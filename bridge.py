import queue
import threading
import time
import comtypes
import soundcard as sc
import numpy as np
from dsp import amplify, output_channels
from delay import SampleDelay, validate_delay
from calibration import CalibrationSettings, CalibrationSignal
from dataclasses import dataclass


@dataclass
class AudioPacket:
    data: object
    generation: int


def offer_latest(buffer, data):
    """A slow output must not stall other devices or build up old audio."""
    try:
        buffer.put_nowait(data)
    except queue.Full:
        try:
            buffer.get_nowait()
        except queue.Empty:
            pass
        buffer.put_nowait(data)


class Bridge:
    def __init__(self):
        self.gain = 100.0
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.thread = None
        self.error = None
        self.outputs = ()
        self._writers = []
        self._error_lock = threading.Lock()
        self._delay_lock = threading.Lock()
        self._delays = {}
        self._calibration_lock = threading.Lock()
        self._calibration = None
        self._generation = 0
        self.calibration_only = False

    @property
    def calibrating(self):
        with self._calibration_lock:
            return self._calibration is not None

    def _set_calibration(self, settings):
        with self._calibration_lock:
            # Sound/level changes preserve timing; transport/solo changes flush old audio.
            previous = self._calibration
            if previous is None or settings is None or previous.outputs != settings.outputs or previous.audition != settings.audition:
                self._generation += 1
            self._calibration = settings

    def start_calibration(self, outputs, pattern='click', level=20, audition='both'):
        settings = CalibrationSettings(tuple(outputs), pattern, level, audition)
        running = self.thread and self.thread.is_alive()
        if running:
            if not self.ready.is_set() or self.error:
                raise RuntimeError('Wait for the audio bridge to finish starting.')
            if any(output not in self.outputs for output in settings.outputs):
                raise ValueError('Choose two outputs already used by the current bridge, or stop it first.')
            self._set_calibration(settings)
            return
        if any(writer.is_alive() for writer in self._writers):
            raise RuntimeError('An audio device is still stopping. Try again shortly.')
        self._set_calibration(settings)
        try:
            self.start(None, settings.outputs)
        except Exception:
            self._set_calibration(None)
            raise

    def update_calibration(self, outputs, pattern='click', level=20, audition='both'):
        if self.calibrating:
            settings = CalibrationSettings(tuple(outputs), pattern, level, audition)
            if any(output not in self.outputs for output in settings.outputs):
                raise ValueError('A chosen output is not playing in the current test.')
            self._set_calibration(settings)

    def end_calibration(self):
        if self.calibration_only:
            self.stop()
        else:
            self._set_calibration(None)

    def set_delay(self, output_id, milliseconds):
        value = validate_delay(milliseconds)
        with self._delay_lock:
            self._delays[output_id] = value

    def get_delay(self, output_id):
        with self._delay_lock:
            return self._delays.get(output_id, 0)

    def start(self, source_id, output_ids, loopback=True):
        if (self.thread and self.thread.is_alive()) or any(w.is_alive() for w in self._writers):
            raise RuntimeError("Stop the existing audio bridge first.")
        outputs = (output_ids,) if isinstance(output_ids, str) else tuple(dict.fromkeys(output_ids))
        if not outputs:
            raise ValueError("Choose at least one output device.")
        if source_id in outputs:
            raise ValueError("The bridge source cannot also be an output (audio feedback).")
        self.outputs = outputs
        self.calibration_only = source_id is None
        if source_id is not None:
            self._set_calibration(None)
        self.stop_event.clear()
        while not self.events.empty():
            self.events.get_nowait()
        self.ready.clear()
        self.error = None
        self._writers = []
        self.thread = threading.Thread(target=self._run, args=(source_id, outputs, loopback), daemon=True)
        self.thread.start()

    def _fail(self, message):
        with self._error_lock:
            if self.error is None and not self.stop_event.is_set():
                self.error = message
                self.events.put(("error", message))
        self.stop_event.set()

    def _write(self, output_id, buffer, started):
        comtypes.CoInitialize()
        try:
            target = sc.get_speaker(output_id)
            channels = min(target.channels, 2)
            delay = SampleDelay(samplerate=48000)
            generation = None
            with target.player(samplerate=48000, channels=channels, blocksize=960) as player:
                started.set()
                while not self.stop_event.is_set():
                    try:
                        packet = buffer.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if packet.generation != self._generation:
                        continue
                    if generation != packet.generation:
                        delay = SampleDelay(samplerate=48000)
                        generation = packet.generation
                    mapped = output_channels(packet.data, channels)
                    player.play(delay.process(mapped, self.get_delay(output_id)))
        except Exception as exc:
            self._fail(f"Output device failed: {exc}")
        finally:
            started.set()
            comtypes.CoUninitialize()

    def _run(self, source_id, output_ids, loopback):
        comtypes.CoInitialize()
        try:
            source = sc.get_microphone(source_id, include_loopback=loopback) if source_id is not None else None
            buffers, startup = [], []
            for output_id in output_ids:
                buffer, started = queue.Queue(maxsize=6), threading.Event()
                writer = threading.Thread(target=self._write, args=(output_id, buffer, started), daemon=True)
                self._writers.append(writer)
                buffers.append(buffer)
                startup.append(started)
                writer.start()
            deadline = time.monotonic() + 5
            for started in startup:
                if not started.wait(timeout=max(0, deadline - time.monotonic())):
                    raise RuntimeError("An output device did not start. Check that it is connected and available.")
            if self.stop_event.is_set():
                return
            generator = CalibrationSignal()
            signal_generation = [-1]
            def broadcast(data):
                nonlocal generator
                with self._calibration_lock:
                    settings, generation = self._calibration, self._generation
                if settings:
                    if signal_generation[0] != generation:
                        generator = CalibrationSignal()
                        signal_generation[0] = generation
                    test = generator.render(len(data), settings.pattern, settings.level)
                    silence = np.zeros_like(test)
                else:
                    data = amplify(data, self.gain)
                for output_id, buffer in zip(output_ids, buffers):
                    samples = (test if settings.audible(output_id) else silence) if settings else data
                    offer_latest(buffer, AudioPacket(samples, generation))
            if source is None:
                self.ready.set()
                self.events.put(("ready", 'Calibration outputs are ready.'))
                deadline = time.monotonic()
                silence = np.zeros((960, 2), dtype=np.float32)
                while not self.stop_event.is_set():
                    broadcast(silence)
                    deadline += .02
                    if time.monotonic() - deadline > .12:
                        deadline = time.monotonic()
                    self.stop_event.wait(timeout=max(0, deadline - time.monotonic()))
                return
            # Preserve stereo/multichannel WASAPI capture; writers map their channels.
            with source.recorder(samplerate=48000, channels=source.channels, blocksize=960) as recorder:
                self.ready.set()
                self.events.put(("ready", f"Audio bridge is playing on {len(output_ids)} output device(s)."))
                while not self.stop_event.is_set():
                    broadcast(recorder.record(numframes=960))
        except Exception as exc:
            self._fail(str(exc))
        finally:
            self.stop_event.set()
            self.ready.set()
            comtypes.CoUninitialize()

    def stop(self):
        self.stop_event.set()
        self._set_calibration(None)
        deadline = time.monotonic() + 3
        if self.thread:
            self.thread.join(timeout=max(0, deadline - time.monotonic()))
        for writer in self._writers:
            writer.join(timeout=max(0, deadline - time.monotonic()))
        if (self.thread and self.thread.is_alive()) or any(w.is_alive() for w in self._writers):
            raise RuntimeError("An audio driver is still stopping. Try again shortly.")
        self.thread = None
        self._writers = []
        self.calibration_only = False

"""Identical transient test audio for every output, on a single sample clock."""
from dataclasses import dataclass
import math
import numpy as np

PATTERNS = {
    'Short click (recommended)': 'click', 'Woodblock': 'woodblock',
    'Bright ding': 'ding', 'Soft bell': 'bell', 'Bass bump': 'bass',
    'Soft noise burst': 'burst',
}
TEMPO_PRESETS = (30, 60, 90, 120, 150, 180, 240)


def validate_tempo(bpm):
    value = float(bpm)
    if not math.isfinite(value) or not 30 <= value <= 240:
        raise ValueError('Tempo must be between 30 and 240 BPM.')
    return value
AUDITIONS = ('both', 'a', 'b')


@dataclass(frozen=True)
class CalibrationSettings:
    outputs: tuple
    pattern: str = 'click'
    level: float = 20
    audition: str = 'both'
    bpm: float = 90

    def __post_init__(self):
        if len(self.outputs) != 2 or len(set(self.outputs)) != 2:
            raise ValueError('Choose two different output devices.')
        if self.pattern not in PATTERNS.values() or self.audition not in AUDITIONS:
            raise ValueError('Invalid calibration sound or listening mode.')
        if not math.isfinite(float(self.level)) or not 0 <= float(self.level) <= 100:
            raise ValueError('Test volume must be between 0 and 100%.')
        validate_tempo(self.bpm)

    def audible(self, output):
        return output in self.outputs and (self.audition == 'both' or output == self.outputs[0 if self.audition == 'a' else 1])


class CalibrationSignal:
    def __init__(self, samplerate=48000):
        self.samplerate = samplerate
        self.position = 0
        self.period = round(2 * samplerate)
        self.start_silence = round(.5 * samplerate)
        self.tempo = None
        self.anchor = 0
        self.pulses = {}
        for pattern, seconds in (('click', .005), ('burst', .020)):
            count = round(seconds * samplerate)
            noise = np.random.default_rng(2026).standard_normal(count)
            spectrum = np.fft.rfft(noise)
            frequencies = np.fft.rfftfreq(count, 1 / samplerate)
            spectrum[(frequencies < 300) | (frequencies > 8000)] = 0
            pulse = np.fft.irfft(spectrum, n=count) * np.hanning(count)
            pulse /= max(float(np.max(np.abs(pulse))), 1e-9)
            self.pulses[pattern] = pulse.astype(np.float32)
        for pattern, seconds in (('woodblock', .04), ('ding', .12), ('bell', .22), ('bass', .14)):
            t = np.arange(round(seconds * samplerate)) / samplerate
            if pattern == 'woodblock':
                pulse = (np.sin(2 * np.pi * 900 * t) + .5 * np.sin(2 * np.pi * 1470 * t)) * np.exp(-t * 140)
            elif pattern == 'ding':
                pulse = (np.sin(2 * np.pi * 1250 * t) + .3 * np.sin(2 * np.pi * 2500 * t)) * np.exp(-t * 32)
            elif pattern == 'bell':
                pulse = sum(weight * np.sin(2 * np.pi * frequency * t) * np.exp(-t * decay)
                            for frequency, weight, decay in ((660, 1, 18), (1390, .55, 26), (1810, .3, 36)))
            else:
                phase = 2 * np.pi * (65 * t + (160 - 65) * .015 * (1 - np.exp(-t / .015)))
                pulse = (np.sin(phase) + .2 * np.sin(2 * phase)) * np.exp(-t * 38)
            attack = max(2, round(.001 * samplerate))
            release = max(2, round(.008 * samplerate))
            pulse[:attack] *= np.linspace(0, 1, attack)
            pulse[-release:] *= np.linspace(1, 0, release)
            pulse /= max(float(np.max(np.abs(pulse))), 1e-9)
            self.pulses[pattern] = pulse.astype(np.float32)

    def render(self, frames, pattern='click', level=20, bpm=90):
        if pattern not in self.pulses or not math.isfinite(float(level)) or not 0 <= level <= 100:
            raise ValueError('Invalid calibration sound settings.')
        bpm = validate_tempo(bpm)
        if self.tempo != bpm:
            self.tempo = bpm
            self.period = round(60 * self.samplerate / bpm)
            self.anchor = self.position
        indices = self.position + np.arange(frames) - self.anchor - self.start_silence
        phase = indices % self.period
        pulse = self.pulses[pattern]
        active = (indices >= 0) & (phase < len(pulse))
        data = np.zeros(frames, dtype=np.float32)
        # Even at 100%, the test peak is bounded to 0.2 (-14 dBFS); normal boost is bypassed.
        data[active] = pulse[phase[active]] * (.2 * float(level) / 100)
        self.position += frames
        return np.repeat(data[:, None], 2, axis=1)

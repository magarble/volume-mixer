"""Identical transient test audio for every output, on a single sample clock."""
from dataclasses import dataclass
import math
import numpy as np

PATTERNS = {'Short click (recommended)': 'click', 'Soft noise burst': 'burst'}
AUDITIONS = ('both', 'a', 'b')


@dataclass(frozen=True)
class CalibrationSettings:
    outputs: tuple
    pattern: str = 'click'
    level: float = 20
    audition: str = 'both'

    def __post_init__(self):
        if len(self.outputs) != 2 or len(set(self.outputs)) != 2:
            raise ValueError('Choose two different output devices.')
        if self.pattern not in PATTERNS.values() or self.audition not in AUDITIONS:
            raise ValueError('Invalid calibration sound or listening mode.')
        if not math.isfinite(float(self.level)) or not 0 <= float(self.level) <= 100:
            raise ValueError('Test volume must be between 0 and 100%.')

    def audible(self, output):
        return output in self.outputs and (self.audition == 'both' or output == self.outputs[0 if self.audition == 'a' else 1])


class CalibrationSignal:
    def __init__(self, samplerate=48000):
        self.samplerate = samplerate
        self.position = 0
        self.period = round(2 * samplerate)
        self.start_silence = round(.5 * samplerate)
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

    def render(self, frames, pattern='click', level=20):
        if pattern not in self.pulses or not math.isfinite(float(level)) or not 0 <= level <= 100:
            raise ValueError('Invalid calibration sound settings.')
        indices = self.position + np.arange(frames) - self.start_silence
        phase = indices % self.period
        pulse = self.pulses[pattern]
        active = (indices >= 0) & (phase < len(pulse))
        data = np.zeros(frames, dtype=np.float32)
        # Even at 100%, the test peak is bounded to 0.2 (-14 dBFS); normal boost is bypassed.
        data[active] = pulse[phase[active]] * (.2 * float(level) / 100)
        self.position += frames
        return np.repeat(data[:, None], 2, axis=1)

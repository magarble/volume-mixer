"""A bounded, sample-based delay; hardware playback still runs continuously."""
import math
import numpy as np

MAX_DELAY_MS = 1000
DELAY_PRESETS = {
    'No added delay (0 ms)': 0,
    'Small offset (50 ms)': 50,
    '100 ms': 100,
    '150 ms': 150,
    '200 ms': 200,
    '250 ms': 250,
    '300 ms': 300,
    '500 ms': 500,
}


def validate_delay(value):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= MAX_DELAY_MS:
        raise ValueError(f'Delay must be between 0 and {MAX_DELAY_MS} ms.')
    return round(number)


class SampleDelay:
    def __init__(self, samplerate=48000):
        self.samplerate = samplerate
        self.chunk_size = 2048
        self.capacity = round(samplerate * MAX_DELAY_MS / 1000) + self.chunk_size
        self.buffer = None
        self.position = 0
        self.previous_delay = None

    def process(self, samples, milliseconds):
        frames = round(validate_delay(milliseconds) * self.samplerate / 1000)
        samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim != 2:
            raise ValueError('Audio must have frames and channels.')
        if self.buffer is None:
            self.buffer = np.zeros((self.capacity, samples.shape[1]), dtype=np.float32)
        if self.buffer.shape[1] != samples.shape[1]:
            raise ValueError('Channel count changed during playback.')
        result = np.empty_like(samples)
        previous = frames if self.previous_delay is None else self.previous_delay
        fade_frames = min(len(samples), round(self.samplerate * .01)) if previous != frames else 0
        for offset in range(0, len(samples), self.chunk_size):
            block = samples[offset:offset + self.chunk_size]
            indices = self.position + np.arange(len(block))
            self.buffer[indices % self.capacity] = block
            delayed = self.buffer[(indices - frames) % self.capacity]
            # Crossfade the tap for 10 ms when adjusted live, avoiding a sharp cut.
            count = min(len(block), max(0, fade_frames - offset))
            if count:
                old = self.buffer[(indices[:count] - previous) % self.capacity]
                weight = ((np.arange(count) + offset + 1) / fade_frames)[:, None]
                delayed[:count] = old * (1 - weight) + delayed[:count] * weight
            result[offset:offset + len(block)] = delayed
            self.position = (self.position + len(block)) % self.capacity
        if len(samples):
            self.previous_delay = frames
        return result

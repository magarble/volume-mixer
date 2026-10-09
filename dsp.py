"""Gain is sample amplitude: 200% = +6.02 dB, with hard clipping protection."""
import numpy as np


def amplify(samples, percent):
    if not 0 <= percent <= 200:
        raise ValueError("Gain must be between 0 and 200%")
    return np.clip(samples * (percent / 100.0), -1.0, 1.0).astype(np.float32)


def output_channels(samples, channels):
    """Handle mono microphones, stereo outputs and multichannel loopback."""
    if channels == 1:
        return samples.mean(axis=1, keepdims=True)
    if samples.shape[1] == 1:
        return np.repeat(samples, channels, axis=1)
    return samples[:, :channels]

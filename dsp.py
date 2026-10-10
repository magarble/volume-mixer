"""Channel mapping for shared audio playback."""
import numpy as np


def output_channels(samples, channels):
    """Handle mono microphones, stereo outputs and multichannel loopback."""
    if channels == 1:
        return samples.mean(axis=1, keepdims=True)
    if samples.shape[1] == 1:
        return np.repeat(samples, channels, axis=1)
    return samples[:, :channels]

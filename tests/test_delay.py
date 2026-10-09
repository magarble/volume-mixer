import unittest
import numpy as np
from delay import SampleDelay, validate_delay


class SampleDelayTests(unittest.TestCase):
    def test_impulse_is_delayed_by_exact_sample_count(self):
        delay = SampleDelay()
        source = np.zeros((4800, 2), dtype=np.float32)
        source[0] = [.5, -.25]
        result = np.concatenate([delay.process(source[i:i + 960], 50) for i in range(0, 4800, 960)])
        np.testing.assert_array_equal(result[:2400], 0)
        np.testing.assert_array_equal(result[2400], [.5, -.25])
        self.assertEqual(np.count_nonzero(result), 2)

    def test_ring_wrap_and_irregular_blocks_preserve_audio(self):
        source = np.arange(14000, dtype=np.float32).reshape(-1, 2)
        delay = SampleDelay(samplerate=1000)
        result = np.concatenate([delay.process(source[i:i + 337], 73) for i in range(0, len(source), 337)])
        np.testing.assert_array_equal(result[:73], 0)
        np.testing.assert_array_equal(result[73:], source[:-73])

    def test_maximum_delay_with_large_blocks(self):
        source = np.arange(7000, dtype=np.float32).reshape(-1, 1)
        result = SampleDelay(samplerate=1000).process(source, 1000)
        np.testing.assert_array_equal(result[:1000], 0)
        np.testing.assert_array_equal(result[1000:], source[:-1000])

    def test_zero_delay_and_live_change_use_existing_history(self):
        delay = SampleDelay(samplerate=1000)
        first = np.arange(100, dtype=np.float32).reshape(-1, 1)
        np.testing.assert_array_equal(delay.process(first, 0), first)
        second = np.arange(100, 200, dtype=np.float32).reshape(-1, 1)
        result = delay.process(second, 50)
        # After the short crossfade, read already captured history, without a new silent gap.
        np.testing.assert_array_equal(result[10:, 0], np.arange(60, 150))
        result = delay.process(np.arange(200, 300, dtype=np.float32).reshape(-1, 1), 0)
        np.testing.assert_array_equal(result[10:, 0], np.arange(210, 300))

    def test_invalid_values_are_rejected(self):
        for value in (-1, 1001, float('nan'), float('inf'), 'invalid'):
            with self.assertRaises(ValueError):
                validate_delay(value)
        self.assertEqual(validate_delay(149.7), 150)

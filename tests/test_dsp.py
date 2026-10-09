import unittest
import numpy as np
from dsp import amplify


class GainTests(unittest.TestCase):
    def test_double_amplitude_and_clip_peaks(self):
        data = np.array([[.2, -.3], [.8, -.9]], dtype=np.float32)
        np.testing.assert_allclose(amplify(data, 200), [[.4, -.6], [1, -1]])
        np.testing.assert_allclose(data, [[.2, -.3], [.8, -.9]])

    def test_unity_and_silence(self):
        data = np.array([[.1, -.7]], dtype=np.float32)
        np.testing.assert_array_equal(amplify(data, 100), data)
        np.testing.assert_array_equal(amplify(data, 0), np.zeros_like(data))

    def test_invalid_gain(self):
        for value in (-1, 201):
            with self.assertRaises(ValueError):
                amplify(np.zeros((1, 2)), value)


if __name__ == '__main__':
    unittest.main()

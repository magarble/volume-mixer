import time
import unittest
from unittest.mock import patch
import numpy as np
from calibration import CalibrationSignal, CalibrationSettings
from bridge import Bridge
from test_bridge import Source, Target


class SignalTests(unittest.TestCase):
    def test_clicks_are_short_identical_stereo_and_spaced(self):
        data = CalibrationSignal().render(3 * 48000)
        np.testing.assert_array_equal(data[:, 0], data[:, 1])
        self.assertEqual(np.count_nonzero(data[:24000]), 0)
        self.assertGreater(np.count_nonzero(data[24000:24240]), 0)
        self.assertEqual(np.count_nonzero(data[24240:120000]), 0)
        np.testing.assert_array_equal(data[24000:24240], data[120000:120240])
        self.assertLessEqual(float(np.max(np.abs(data))), .040001)

    def test_chunking_does_not_change_signal_or_timing(self):
        full = CalibrationSignal().render(144000, pattern='burst', level=80)
        generator = CalibrationSignal()
        streamed = np.concatenate([generator.render(960, 'burst', 80) for _ in range(150)])
        np.testing.assert_array_equal(full, streamed)

    def test_zero_volume_and_peak_bound(self):
        np.testing.assert_array_equal(CalibrationSignal().render(48000, level=0), 0)
        self.assertLessEqual(float(np.max(np.abs(CalibrationSignal().render(48000, level=100)))), .200001)

    def test_bad_pair_and_bad_settings(self):
        for outputs in ((), ('headset',), ('headset', 'headset')):
            with self.assertRaises(ValueError):
                CalibrationSettings(outputs)
        for options in ({'level': float('nan')}, {'level': 101}, {'pattern': 'unknown'}, {'audition': 'other'}):
            with self.assertRaises(ValueError):
                CalibrationSettings(('a', 'b'), **options)


class CalibrationPlaybackTests(unittest.TestCase):
    def wait_for_blocks(self, targets, count):
        deadline = time.monotonic() + 2
        while min(len(t.blocks) for t in targets.values()) < count and time.monotonic() < deadline:
            time.sleep(.005)
        self.assertGreaterEqual(min(len(t.blocks) for t in targets.values()), count)

    def test_standalone_clicks_need_no_capture_and_use_output_delay(self):
        targets = {'a': Target(2), 'b': Target(2)}
        bridge = Bridge()
        bridge.set_delay('a', 40)
        with patch('bridge.sc.get_speaker', side_effect=targets.__getitem__), patch('bridge.sc.get_microphone') as capture:
            bridge.start_calibration(('a', 'b'))
            try:
                self.assertTrue(bridge.ready.wait(2))
                self.wait_for_blocks(targets, 30)
                self.assertIsNone(bridge.error)
                a = np.concatenate(targets['a'].blocks)
                b = np.concatenate(targets['b'].blocks)
                first_a = int(np.flatnonzero(a[:, 0])[0])
                first_b = int(np.flatnonzero(b[:, 0])[0])
                self.assertEqual(first_a - first_b, 1920)
                capture.assert_not_called()
            finally:
                bridge.end_calibration()
        self.assertFalse(bridge.calibrating)
        self.assertIsNone(bridge.thread)

    def test_live_bridge_calibration_bypasses_boost_and_resumes_source(self):
        targets = {'a': Target(2), 'b': Target(2)}
        bridge = Bridge()
        bridge.gain = 200
        with patch('bridge.sc.get_speaker', side_effect=targets.__getitem__), patch('bridge.sc.get_microphone', return_value=Source()):
            bridge.start('cable', ('a', 'b'))
            try:
                self.assertTrue(bridge.ready.wait(2))
                self.wait_for_blocks(targets, 3)
                np.testing.assert_allclose(targets['a'].blocks[-1], .4)
                bridge.start_calibration(('a', 'b'), audition='a')
                counts = {name: len(t.blocks) for name, t in targets.items()}
                self.wait_for_blocks(targets, max(counts.values()) + 30)
                a = np.concatenate(targets['a'].blocks[counts['a'] + 2:])
                b = np.concatenate(targets['b'].blocks[counts['b'] + 2:])
                self.assertGreater(np.count_nonzero(a), 0)
                self.assertLessEqual(float(np.max(np.abs(a))), .040001)
                np.testing.assert_array_equal(b, 0)
                bridge.end_calibration()
                self.assertTrue(bridge.thread.is_alive())
                self.wait_for_blocks(targets, max(len(t.blocks) for t in targets.values()) + 3)
                for target in targets.values():
                    np.testing.assert_allclose(target.blocks[-1], .4)
                self.assertEqual(bridge.gain, 200)
            finally:
                bridge.stop()

    def test_live_test_rejects_outputs_outside_current_bridge(self):
        targets = {'a': Target(2), 'b': Target(2)}
        bridge = Bridge()
        with patch('bridge.sc.get_speaker', side_effect=targets.__getitem__), patch('bridge.sc.get_microphone', return_value=Source()):
            bridge.start('cable', ('a', 'b'))
            try:
                self.assertTrue(bridge.ready.wait(2))
                with self.assertRaises(ValueError):
                    bridge.start_calibration(('a', 'new-output'))
                self.assertFalse(bridge.calibrating)
            finally:
                bridge.stop()

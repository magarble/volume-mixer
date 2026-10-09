import queue
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
from bridge import Bridge, offer_latest
from dsp import output_channels


class Recorder:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def record(self, numframes):
        time.sleep(.005)
        return np.full((numframes, 1), .2, dtype=np.float32)


class Source:
    channels = 1

    def recorder(self, **kwargs):
        return Recorder()


class Target:
    def __init__(self, channels, delay=0):
        self.channels = channels
        self.delay = delay
        self.blocks = []
        self.opened = threading.Event()

    def player(self, **kwargs):
        return self

    def __enter__(self):
        self.opened.set()
        return self

    def __exit__(self, *args):
        pass

    def play(self, data):
        time.sleep(self.delay)
        self.blocks.append(data.copy())


class BridgeTests(unittest.TestCase):
    def test_fan_out_gain_and_slow_output_independence(self):
        targets = {'headset': Target(2), 'bluetooth': Target(1, delay=.08)}
        bridge = Bridge()
        bridge.gain = 200
        with patch('bridge.sc.get_microphone', return_value=Source()), patch('bridge.sc.get_speaker', side_effect=targets.__getitem__):
            bridge.start('cable', ('headset', 'bluetooth', 'headset'))
            try:
                self.assertTrue(bridge.ready.wait(2))
                self.assertIsNone(bridge.error)
                time.sleep(.3)
            finally:
                bridge.stop()
        self.assertEqual(bridge.outputs, ('headset', 'bluetooth'))
        self.assertGreater(len(targets['headset'].blocks), len(targets['bluetooth'].blocks) * 2)
        for name, target in targets.items():
            self.assertTrue(target.blocks, name)
            self.assertEqual(target.blocks[0].shape[1], target.channels)
            np.testing.assert_allclose(target.blocks[0], .4)

    def test_output_failure_never_reports_success(self):
        bridge = Bridge()
        with patch('bridge.sc.get_microphone', return_value=Source()), patch('bridge.sc.get_speaker', side_effect=OSError('disconnected')):
            bridge.start('cable', ('headset', 'bluetooth'))
            self.assertTrue(bridge.ready.wait(2))
            bridge.stop()
        self.assertIn('disconnected', bridge.error)
        events = []
        while not bridge.events.empty():
            events.append(bridge.events.get_nowait()[0])
        self.assertEqual(events, ['error'])

    def test_invalid_destinations(self):
        bridge = Bridge()
        for outputs in ((), ('headset', 'cable')):
            with self.assertRaises(ValueError):
                bridge.start('cable', outputs)

    def test_queue_keeps_recent_audio(self):
        buffer = queue.Queue(maxsize=2)
        for block in range(4):
            offer_latest(buffer, block)
        self.assertEqual([buffer.get_nowait(), buffer.get_nowait()], [2, 3])

    def test_downmix_and_mono_expansion(self):
        stereo = np.array([[.2, .6], [-.2, -.6]], dtype=np.float32)
        np.testing.assert_allclose(output_channels(stereo, 1), [[.4], [-.4]])
        np.testing.assert_allclose(output_channels(stereo[:, :1], 2), [[.2, .2], [-.2, -.2]])

    def test_delay_is_independent_and_adjustable_during_playback(self):
        targets = {'headset': Target(2), 'bluetooth': Target(2)}
        bridge = Bridge()
        bridge.set_delay('headset', 40)
        with patch('bridge.sc.get_microphone', return_value=Source()), patch('bridge.sc.get_speaker', side_effect=targets.__getitem__):
            bridge.start('cable', ('headset', 'bluetooth'))
            try:
                self.assertTrue(bridge.ready.wait(2))
                deadline = time.monotonic() + 2
                while min(len(t.blocks) for t in targets.values()) < 4 and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertGreaterEqual(min(len(t.blocks) for t in targets.values()), 4)
                np.testing.assert_array_equal(targets['headset'].blocks[0], 0)
                np.testing.assert_array_equal(targets['headset'].blocks[1], 0)
                np.testing.assert_allclose(targets['headset'].blocks[2], .2)
                np.testing.assert_allclose(targets['bluetooth'].blocks[0], .2)
                bridge.set_delay('headset', 0)
                self.assertEqual(bridge.get_delay('headset'), 0)
                self.assertEqual(bridge.get_delay('bluetooth'), 0)
                self.assertTrue(bridge.thread.is_alive())
            finally:
                bridge.stop()

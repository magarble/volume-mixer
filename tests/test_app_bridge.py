import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from app import Mixer


class BridgeLifecycleTests(unittest.TestCase):
    def make_mixer(self):
        mixer = object.__new__(Mixer)
        mixer.pending_share = None
        mixer.shared_route = None
        mixer.primary_output_id = ''
        mixer.bridge_outputs = ()
        mixer.bridge_name = ''
        mixer.bridge = SimpleNamespace(thread=None, events=queue.Queue(), start=Mock(), start_process=Mock(), stop=Mock())
        self.original = ('console-before', '', 'communications-before')
        self.source = SimpleNamespace(id='cable', FriendlyName='Dedicated Virtual Cable')
        self.headset = SimpleNamespace(id='headset', FriendlyName='Headset')
        self.bluetooth = SimpleNamespace(id='bluetooth', FriendlyName='Bluetooth speaker')
        self.program = SimpleNamespace(pid=42, name='Spotify')
        mixer.audio = SimpleNamespace(
            routing=SimpleNamespace(snapshot=Mock(return_value=self.original)),
            outputs=[self.source, self.headset, self.bluetooth],
            refresh=Mock(return_value=[]), route=Mock())
        mixer.status = Mock()
        mixer._refresh = Mock()
        mixer.after = Mock()
        mixer.check_shared_playback = Mock()
        return mixer

    def add_calibration_controls(self, mixer, standalone):
        mixer.calibration_controls = Mock()
        mixer.calibration_status = Mock()
        mixer.calibration_selection = ()
        mixer.build_sync_device_cards = Mock()
        mixer.bridge.calibration_only = standalone
        mixer.bridge.calibrating = False
        mixer.bridge.start_calibration = Mock()
        mixer.bridge.end_calibration = Mock()
        mixer.bridge.update_calibration = Mock()

    def test_standalone_alignment_changes_no_program_routing(self):
        mixer = self.make_mixer()
        self.add_calibration_controls(mixer, standalone=True)
        mixer.start_alignment_test(('headset', 'bluetooth'), {'pattern': 'click', 'level': 20, 'audition': 'both'})
        self.assertEqual(mixer.bridge_outputs, ('headset', 'bluetooth'))
        mixer.audio.route.assert_not_called()
        mixer.stop_alignment_test()
        self.assertEqual(mixer.bridge_outputs, ())
        mixer.audio.route.assert_not_called()
        mixer.bridge.end_calibration.assert_called_once()

    def test_live_alignment_rejected_without_changing_active_route(self):
        mixer = self.make_mixer()
        self.add_calibration_controls(mixer, standalone=False)
        mixer.shared_route = (42, self.original)
        mixer.bridge.thread = SimpleNamespace(is_alive=lambda: True)
        mixer.bridge_outputs = ('headset', 'bluetooth')
        mixer.action = lambda callback: callback()
        with self.assertRaisesRegex(RuntimeError, 'Stop sharing'):
            mixer.start_alignment_test(('headset', 'bluetooth'), {'pattern': 'click', 'level': 20, 'audition': 'both'})
        mixer.bridge.start_calibration.assert_not_called()
        self.assertEqual(mixer.shared_route, (42, self.original))
        self.assertEqual(mixer.bridge_outputs, ('headset', 'bluetooth'))
        mixer.audio.route.assert_not_called()

    def test_failed_bridge_must_restore_before_new_alignment(self):
        mixer = self.make_mixer()
        self.add_calibration_controls(mixer, standalone=True)
        mixer.shared_route = (42, self.original)
        mixer.action = lambda callback: callback()
        with self.assertRaises(RuntimeError):
            mixer.start_alignment_test(('headset', 'bluetooth'), {'pattern': 'click', 'level': 20, 'audition': 'both'})
        mixer.bridge.start_calibration.assert_not_called()
        self.assertEqual(mixer.shared_route, (42, self.original))

    @patch('app.AudioUtilities.GetSpeakers')
    def test_route_only_after_outputs_ready_then_restore_exact_preferences(self, default):
        mixer = self.make_mixer()
        default.return_value = self.headset
        mixer.start_program_bridge(self.program, ('bluetooth', 'headset'))
        mixer.bridge.start_process.assert_called_once_with(42, ('headset',))
        mixer.audio.route.assert_not_called()
        mixer.bridge.events.put(('ready', 'ready'))
        mixer.poll()
        mixer.audio.route.assert_called_once_with(42, 'bluetooth')
        self.assertEqual(mixer.bridge_outputs, ('bluetooth', 'headset'))
        mixer.stop_sharing()
        self.assertEqual(mixer.audio.route.call_args.args, (42, self.original))
        self.assertIsNone(mixer.shared_route)
        self.assertEqual(mixer.bridge_outputs, ())
        mixer.bridge.stop.assert_called_once()

    @patch('app.AudioUtilities.GetSpeakers')
    def test_output_disconnect_restores_program_route(self, default):
        mixer = self.make_mixer()
        default.return_value = self.headset
        mixer.start_program_bridge(self.program, ('bluetooth', 'headset'))
        mixer.bridge.events.put(('ready', 'ready'))
        mixer.poll()
        mixer.bridge.events.put(('error', 'Bluetooth disconnected'))
        mixer.poll()
        self.assertEqual(mixer.audio.route.call_args.args, (42, self.original))
        self.assertIsNone(mixer.shared_route)
        mixer.bridge.stop.assert_called_once()

    @patch('app.AudioUtilities.GetSpeakers')
    def test_start_failure_keeps_original_routing(self, default):
        mixer = self.make_mixer()
        default.return_value = self.headset
        mixer.bridge.start_process.side_effect = OSError('Device unavailable')
        with self.assertRaises(OSError):
            mixer.start_program_bridge(self.program, ('bluetooth', 'headset'))
        mixer.audio.route.assert_not_called()
        self.assertIsNone(mixer.pending_share)
        self.assertEqual(mixer.bridge_outputs, ())

from types import SimpleNamespace
import unittest
from unittest.mock import patch
from output_rows import OutputPlan, output_letter
import test_app_bridge as helpers


class OutputPlanTests(unittest.TestCase):
    def test_add_remove_and_labels(self):
        plan = OutputPlan(['headset'])
        plan.add()
        plan.add()
        plan.outputs[1:] = ['bluetooth', 'speakers']
        plan.remove(1)
        self.assertEqual(plan.outputs, ['headset', 'speakers'])
        self.assertEqual([output_letter(i) for i in (0, 1, 2, 25, 26)], ['A', 'B', 'C', 'Z', 'AA'])
        with self.assertRaises(ValueError):
            plan.remove(0)

    def test_default_output_resolution_and_duplicate_rejection(self):
        self.assertEqual(OutputPlan(['', 'bluetooth']).resolve('headset'), ('headset', 'bluetooth'))
        for outputs in (['', 'headset'], ['headset', 'headset'], ['headset', None]):
            with self.assertRaises(ValueError):
                OutputPlan(outputs).resolve('headset')


class InlineRoutingTests(unittest.TestCase):
    def setUp(self):
        helper = helpers.BridgeLifecycleTests()
        self.mixer = helper.make_mixer()
        self.program, self.headset, self.source = helper.program, helper.headset, helper.source
        self.original = helper.original
        self.mixer.output_plans = {}
        self.mixer.programs = []
        self.mixer.active_source_id = ''
        self.mixer.bridge.stop.side_effect = lambda: setattr(self.mixer.bridge, 'thread', None)

    @patch('app.AudioUtilities.GetSpeakers')
    def test_apply_inline_pair_starts_bridge_without_routing_until_ready(self, default):
        default.return_value = self.headset
        plan = OutputPlan(['', 'bluetooth'], 'cable')
        self.mixer.output_plans[42] = plan
        self.assertTrue(self.mixer.apply_inline_outputs(self.program, plan))
        self.mixer.bridge.start.assert_called_once_with('cable', ('headset', 'bluetooth'))
        self.mixer.audio.route.assert_not_called()
        self.assertEqual(plan.outputs, ['headset', 'bluetooth'])
        self.mixer.bridge.events.put(('ready', 'ready'))
        self.mixer.poll()
        self.mixer.audio.route.assert_called_once_with(42, 'cable')

    @patch('app.AudioUtilities.GetSpeakers')
    def test_invalid_draft_keeps_existing_playback(self, default):
        default.return_value = self.headset
        self.mixer.shared_route = (42, self.original)
        plan = OutputPlan(['', 'headset'], 'cable')
        with self.assertLogs(level='ERROR'):
            self.assertFalse(self.mixer.apply_inline_outputs(self.program, plan))
        self.mixer.bridge.stop.assert_not_called()
        self.mixer.audio.route.assert_not_called()
        self.assertEqual(self.mixer.shared_route, (42, self.original))

    @patch('app.AudioUtilities.GetSpeakers')
    def test_reconfigure_restores_original_before_starting_new_outputs(self, default):
        default.return_value = self.headset
        self.mixer.audio.outputs.append(SimpleNamespace(id='speakers', FriendlyName='Speakers'))
        self.mixer.shared_route = (42, self.original)
        self.mixer.bridge.thread = SimpleNamespace(is_alive=lambda: True)
        plan = OutputPlan(['headset', 'speakers'], 'cable')
        self.mixer.output_plans[42] = plan
        self.assertTrue(self.mixer.apply_inline_outputs(self.program, plan))
        self.mixer.audio.route.assert_called_once_with(42, self.original)
        self.mixer.bridge.start.assert_called_once_with('cable', ('headset', 'speakers'))

    def test_removing_last_extra_keeps_remaining_output_a(self):
        self.mixer.shared_route = (42, self.original)
        plan = OutputPlan(['headset', 'bluetooth'], 'cable')
        self.mixer.output_plans[42] = plan
        self.mixer.remove_inline_output(self.program, plan, 1)
        self.assertEqual(plan.outputs, ['headset'])
        self.mixer.bridge.stop.assert_called_once()
        self.assertEqual(self.mixer.audio.route.call_args_list[0].args, (42, self.original))
        self.assertEqual(self.mixer.audio.route.call_args_list[1].args, (42, 'headset'))

    def test_stop_single_output_bridge_shows_restored_route(self):
        self.mixer.shared_route = (42, self.original)
        plan = OutputPlan(['headset'], 'cable')
        self.mixer.output_plans[42] = plan
        self.mixer.stop_inline_outputs(self.program, plan)
        self.assertEqual(plan.outputs, [''])

    def test_stale_stop_button_cannot_stop_another_app(self):
        self.mixer.shared_route = (100, self.original)
        self.mixer.stop_inline_outputs(self.program, OutputPlan())
        self.mixer.bridge.stop.assert_not_called()

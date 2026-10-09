import ctypes
import unittest
from routing import Routing


class FakeDLL:
    def __init__(self):
        self.deleted = []

    def WindowsDeleteString(self, ptr):
        self.deleted.append(ptr.value)


class FakeRouting(Routing):
    def __init__(self, fail_role=None):
        self.dll = FakeDLL()
        self.roles = ['console-old', '', 'communications-old']
        self.strings = {}
        self.fail_role = fail_role

    def snapshot(self, pid, flow=0):
        return tuple(self.roles)

    def _string(self, value):
        index = len(self.strings) + 1
        self.strings[index] = value
        return ctypes.c_void_p(index)

    def _call(self, slot, args, pid, flow, role, ptr):
        if role == self.fail_role:
            self.fail_role = None
            raise OSError('simulated device failure')
        value = self.strings.get(ptr.value, '')
        self.roles[role] = value.removeprefix(self.PREFIX).removesuffix(self.SUFFIX[flow])


class RoutingTests(unittest.TestCase):
    def test_failure_restores_each_roles_original_preference(self):
        routing = FakeRouting(fail_role=2)
        original = routing.snapshot(1)
        with self.assertRaises(OSError):
            routing.set(1, 'new-device')
        self.assertEqual(routing.snapshot(1), original)
        self.assertEqual(len(routing.dll.deleted), 5)

    def test_restore_preserves_different_role_preferences(self):
        routing = FakeRouting()
        original = routing.snapshot(1)
        routing.set(1, 'new-device')
        self.assertEqual(routing.snapshot(1), ('new-device',) * 3)
        routing.set(1, original)
        self.assertEqual(routing.snapshot(1), original)

    def test_default_clears_all_roles(self):
        routing = FakeRouting()
        routing.set(1, '')
        self.assertEqual(routing.snapshot(1), ('',) * 3)

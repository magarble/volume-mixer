import unittest
from types import SimpleNamespace
from unittest.mock import patch
from process_capture import CompletionHandler, ensure_supported, _handlers


class ProcessCaptureTests(unittest.TestCase):
    def test_callback_survives_owner_timeout_until_windows_releases_it(self):
        handler = CompletionHandler()
        address = handler.address
        handler.callbacks[1](address)  # Windows holds an asynchronous reference.
        handler.close()
        self.assertTrue(handler.abandoned)
        self.assertIn(address, _handlers)
        handler.callbacks[2](address)
        self.assertNotIn(address, _handlers)
        handler.close()  # Cleanup is idempotent.

    def test_callback_owner_cleanup_without_activation(self):
        handler = CompletionHandler()
        address = handler.address
        handler.close()
        self.assertNotIn(address, _handlers)

    def test_old_windows_build_is_rejected(self):
        with patch('process_capture.sys.getwindowsversion', return_value=SimpleNamespace(build=19045)):
            with self.assertRaisesRegex(RuntimeError, 'Windows build 20348'):
                ensure_supported()

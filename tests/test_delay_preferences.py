import json
from pathlib import Path
import tempfile
import unittest
from delay_preferences import DelayPreferences


class PreferencesTests(unittest.TestCase):
    def test_settings_round_trip_and_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'output-delays.json'
            preferences = DelayPreferences(path)
            preferences.set('headset', 150)
            preferences.set('speaker', 0)
            preferences.save()
            loaded = DelayPreferences(path)
            self.assertEqual(loaded.values['headset'], 150)
            loaded.set('headset', 0)
            loaded.save()
            self.assertEqual(DelayPreferences(path).values['headset'], 0)

    def test_invalid_entries_do_not_discard_valid_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text(json.dumps({'output_delays': {'headset': 120, 'invalid': -5, 'bad': None}}))
            self.assertEqual(DelayPreferences(path).values, {'headset': 120})
            path.write_text('{broken json')
            self.assertEqual(DelayPreferences(path).values, {})

    def test_no_changes_do_not_create_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            preferences = DelayPreferences(path)
            preferences.set('headset', 0)
            preferences.save()
            self.assertFalse(path.exists())

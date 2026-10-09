import unittest
from unittest.mock import patch
from app_names import friendly_name, file_product_name


class NameTests(unittest.TestCase):
    def test_known_apps_and_helpers(self):
        self.assertEqual(friendly_name('Spotify.exe'), 'Spotify')
        self.assertEqual(friendly_name('steamwebhelper.exe'), 'Steam')
        self.assertEqual(friendly_name('DiscordPTB.exe'), 'Discord PTB')

    @patch('app_names.file_product_name', return_value='Example Music Player')
    def test_windows_product_metadata(self, metadata):
        self.assertEqual(friendly_name('helper123.exe', 'C:/example.exe'), 'Example Music Player')

    @patch('app_names.file_product_name', return_value='')
    def test_session_and_filename_fallback(self, metadata):
        self.assertEqual(friendly_name('helper.exe', session_name='My Music'), 'My Music')
        self.assertEqual(friendly_name('MyMusicPlayer.exe'), 'My Music Player')
        self.assertEqual(friendly_name('MyMusicPlayer.exe', session_name='@unresolved-resource'), 'My Music Player')

    def test_missing_file_has_no_metadata(self):
        self.assertEqual(file_product_name('Z:/missing/not-real.exe'), '')

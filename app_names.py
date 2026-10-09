"""Resolve user-facing names without losing the executable/process identity."""
import ctypes as c
from functools import lru_cache
from pathlib import Path
import re

KNOWN_NAMES = {
    'spotify.exe': 'Spotify', 'discord.exe': 'Discord',
    'discordptb.exe': 'Discord PTB', 'discordcanary.exe': 'Discord Canary',
    'chrome.exe': 'Google Chrome', 'msedge.exe': 'Microsoft Edge',
    'firefox.exe': 'Mozilla Firefox', 'opera.exe': 'Opera',
    'steam.exe': 'Steam', 'steamwebhelper.exe': 'Steam',
    'stremio.exe': 'Stremio', 'vlc.exe': 'VLC media player',
    'audiodg.exe': 'Windows Audio', 'nvcontainer.exe': 'NVIDIA Container',
    'nvidia broadcast.exe': 'NVIDIA Broadcast',
    'steelseriessonar.exe': 'SteelSeries Sonar',
}


@lru_cache(maxsize=512)
def file_product_name(path):
    if not path:
        return ''
    try:
        version = c.WinDLL('version', use_last_error=True)
        version.GetFileVersionInfoSizeW.argtypes = [c.c_wchar_p, c.POINTER(c.c_uint32)]
        version.GetFileVersionInfoSizeW.restype = c.c_uint32
        version.GetFileVersionInfoW.argtypes = [c.c_wchar_p, c.c_uint32, c.c_uint32, c.c_void_p]
        version.VerQueryValueW.argtypes = [c.c_void_p, c.c_wchar_p, c.POINTER(c.c_void_p), c.POINTER(c.c_uint32)]
        size = version.GetFileVersionInfoSizeW(path, None)
        if not size:
            return ''
        buffer = c.create_string_buffer(size)
        if not version.GetFileVersionInfoW(path, 0, size, buffer):
            return ''
        pointer, length = c.c_void_p(), c.c_uint32()
        translations = []
        if version.VerQueryValueW(buffer, r'\VarFileInfo\Translation', c.byref(pointer), c.byref(length)):
            words = c.cast(pointer, c.POINTER(c.c_uint16))
            translations = [(words[i], words[i + 1]) for i in range(0, length.value // 2 - 1, 2)]
        translations += [(0x0409, 0x04b0), (0x0409, 0x04e4)]
        for field in ('ProductName', 'FileDescription'):
            for language, codepage in translations:
                key = f'\\StringFileInfo\\{language:04x}{codepage:04x}\\{field}'
                if version.VerQueryValueW(buffer, key, c.byref(pointer), c.byref(length)) and pointer.value:
                    value = c.wstring_at(pointer).strip()
                    if value:
                        return value
    except (OSError, ValueError):
        pass
    return ''


def friendly_name(process_name, executable_path='', session_name=''):
    alias = KNOWN_NAMES.get(process_name.lower())
    if alias:
        return alias
    product = file_product_name(executable_path)
    if product:
        return product
    if session_name and not session_name.startswith(('@', '%')):
        return session_name
    stem = Path(process_name).stem
    stem = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', stem)
    return re.sub(r'[_-]+', ' ', stem).strip() or 'Unknown application'

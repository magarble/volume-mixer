"""Capture the real Windows UI with example data, without accessing audio devices.

Run with the project's Python environment from any directory. Screenshots are
written beside this script. No additional imaging dependencies are required.
"""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from app import Mixer
from delay_preferences import DelayPreferences
from output_rows import OutputPlan


class DemoVolume:
    def GetMasterVolumeLevelScalar(self):
        return .65

    def GetMute(self):
        return False

    def SetMasterVolumeLevelScalar(self, *args):
        pass

    def SetMute(self, *args):
        pass


class DemoAudio:
    def __init__(self):
        def device(id, name):
            return SimpleNamespace(id=id, FriendlyName=name, EndpointVolume=DemoVolume())
        self.outputs = [device('bluetooth', 'Bluetooth speaker'), device('headset', 'Wired headset')]
        self.inputs = [device('microphone', 'Headset microphone')]
        self.routing_error = None
        self.routing = SimpleNamespace(get=lambda pid, flow=0: 'bluetooth' if pid == 4242 and flow == 0 else '', close=lambda: None)

    def refresh(self):
        return [SimpleNamespace(pid=pid, name=name, process_name=process, volume=volume,
                                muted=False, set_volume=lambda value: None,
                                set_mute=lambda value: None)
                for pid, name, process, volume in (
                    (4242, 'Music player', 'music-player.exe', 65),
                    (4243, 'Web browser', 'browser.exe', 35),
                    (4244, 'Voice chat', 'voice-chat.exe', 80))]


def capture(root, target):
    user, gdi = c.WinDLL('user32'), c.WinDLL('gdi32')
    user.GetAncestor.argtypes = [w.HWND, w.UINT]
    user.GetAncestor.restype = w.HWND
    user.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
    user.GetWindowDC.argtypes = [w.HWND]
    user.GetWindowDC.restype = w.HDC
    user.ReleaseDC.argtypes = [w.HWND, w.HDC]
    user.PrintWindow.argtypes = [w.HWND, w.HDC, w.UINT]
    gdi.CreateCompatibleDC.argtypes = [w.HDC]
    gdi.CreateCompatibleDC.restype = w.HDC
    gdi.CreateCompatibleBitmap.argtypes = [w.HDC, c.c_int, c.c_int]
    gdi.CreateCompatibleBitmap.restype = w.HBITMAP
    gdi.SelectObject.argtypes = [w.HDC, w.HANDLE]
    gdi.SelectObject.restype = w.HANDLE
    gdi.DeleteObject.argtypes = [w.HANDLE]
    gdi.DeleteDC.argtypes = [w.HDC]
    gdi.GetDIBits.argtypes = [w.HDC, w.HBITMAP, w.UINT, w.UINT, c.c_void_p, c.c_void_p, w.UINT]
    root.update()
    hwnd = user.GetAncestor(root.winfo_id(), 2)
    rect = w.RECT()
    if not user.GetWindowRect(hwnd, c.byref(rect)):
        raise c.WinError()
    width, height = rect.right - rect.left, rect.bottom - rect.top
    dc = user.GetWindowDC(hwnd)
    memory = gdi.CreateCompatibleDC(dc)
    bitmap = gdi.CreateCompatibleBitmap(dc, width, height)
    previous = gdi.SelectObject(memory, bitmap)
    try:
        if not user.PrintWindow(hwnd, memory, 2):
            raise RuntimeError('Windows could not capture the mixer window.')
        gdi.SelectObject(memory, previous)
        header = c.create_string_buffer(struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0))
        buffer = c.create_string_buffer(width * height * 4)
        if gdi.GetDIBits(memory, bitmap, 0, height, buffer, header, 0) != height:
            raise RuntimeError('Windows could not read the captured pixels.')
        pixels = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
        rgb = pixels[:, :, [2, 1, 0]].copy()
        rows = b''.join(b'\x00' + row.tobytes() for row in rgb)
        def chunk(name, data):
            return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
        target.write_bytes(b'\x89PNG\r\n\x1a\n' +
                           chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
                           chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))
    finally:
        gdi.SelectObject(memory, previous)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory)
        user.ReleaseDC(hwnd, dc)


if __name__ == '__main__':
    preferences = DelayPreferences(ROOT / 'build/example-output-delays.json')
    with patch('app.Audio', DemoAudio), patch('app.DelayPreferences', return_value=preferences):
        root = Mixer()
        try:
            root.geometry('1060x1000+30+20')
            root.output_plans[4242] = OutputPlan(['bluetooth', 'headset'])
            root.calibration_selection = ('headset', 'bluetooth')
            root.delay_variable('headset').set(150)
            root.delay_variable('bluetooth').set(0)
            root._refresh()
            root.status.set('Example setup: choose Bluetooth as Output A and copy to your wired headset.')
            root.update()
            root.after(350, lambda: None)
            capture(root, Path(__file__).with_name('programs.png'))
            root.show_output_sync()
            root.geometry('1060x1300+30+20')
            root.status.set('Example delay: wired headset 150 ms; Bluetooth speaker 0 ms.')
            capture(root, Path(__file__).with_name('output-sync.png'))
        finally:
            root.close()
    print('Captured Programs and Output sync with example data.')

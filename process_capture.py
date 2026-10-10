"""Windows process-loopback capture, implemented using system COM APIs only."""
import ctypes as c
import sys
import threading
import time
import numpy as np
from comtypes import GUID

IAUDIOCLIENT = GUID('{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}')
IAUDIOCAPTURECLIENT = GUID('{C8ADBD64-E71E-48A0-A4DE-185C395CD317}')
_handlers = {}  # Pin COM callbacks until both Windows and their owner release them.


def ensure_supported():
    if sys.platform != 'win32' or sys.getwindowsversion().build < 20348:
        raise RuntimeError('Application sharing requires Windows build 20348 or later (including Windows 11).')


def check(hr):
    if hr < 0:
        raise OSError(f'Windows process capture failed (0x{hr & 0xffffffff:08X}).')


def call(pointer, slot, types, *arguments):
    table = c.cast(pointer, c.POINTER(c.POINTER(c.c_void_p))).contents
    function = c.WINFUNCTYPE(c.c_int32, c.c_void_p, *types)(table[slot])
    result = function(pointer, *arguments)
    check(result)


def release(pointer):
    if pointer:
        call(pointer, 2, [])


class ActivationParameters(c.Structure):
    _fields_ = [('type', c.c_int32), ('pid', c.c_uint32), ('mode', c.c_int32)]


class Blob(c.Structure):
    _fields_ = [('size', c.c_uint32), ('data', c.c_void_p)]


class VariantPayload(c.Union):
    _fields_ = [('blob', Blob), ('padding', c.c_byte * 16)]


class PropVariant(c.Structure):
    _fields_ = [('vt', c.c_uint16), ('reserved', c.c_uint16 * 3), ('payload', VariantPayload)]


class WaveFormat(c.Structure):
    _pack_ = 2
    _fields_ = [('tag', c.c_uint16), ('channels', c.c_uint16), ('rate', c.c_uint32),
                ('bytes_per_second', c.c_uint32), ('alignment', c.c_uint16),
                ('bits', c.c_uint16), ('extra', c.c_uint16)]


class CompletionHandler:
    def __init__(self):
        self.done = threading.Event()
        self.client = c.c_void_p()
        self.error = None
        self.references = 1
        self.lock = threading.RLock()
        self.abandoned = False
        allowed = {bytes(GUID(value)) for value in (
            '{00000000-0000-0000-C000-000000000046}',
            '{41D949AB-9862-444A-80F6-C261334DA5EB}',
            '{94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90}')}
        def query(this, iid, output):
            if c.string_at(iid, 16) in allowed:
                output[0] = self.address
                addref(this)
                return 0
            output[0] = None
            return -2147467262
        def addref(this):
            with self.lock:
                self.references += 1
                return self.references
        def drop(this):
            with self.lock:
                self.references -= 1
                if self.references == 0:
                    _handlers.pop(self.address, None)
                return self.references
        def completed(this, operation):
            unknown = c.c_void_p()
            try:
                result = c.c_int32()
                call(operation, 3, [c.POINTER(c.c_int32), c.POINTER(c.c_void_p)], c.byref(result), c.byref(unknown))
                check(result.value)
                client = c.c_void_p()
                call(unknown, 0, [c.POINTER(GUID), c.POINTER(c.c_void_p)], c.byref(IAUDIOCLIENT), c.byref(client))
                with self.lock:
                    if self.abandoned:
                        release(client)
                    else:
                        self.client = client
            except Exception as exc:
                self.error = exc
            finally:
                release(unknown)
                self.done.set()
            return 0
        self.callbacks = (
            c.WINFUNCTYPE(c.c_int32, c.c_void_p, c.POINTER(GUID), c.POINTER(c.c_void_p))(query),
            c.WINFUNCTYPE(c.c_uint32, c.c_void_p)(addref),
            c.WINFUNCTYPE(c.c_uint32, c.c_void_p)(drop),
            c.WINFUNCTYPE(c.c_int32, c.c_void_p, c.c_void_p)(completed))
        self.table = (c.c_void_p * 4)(*(c.cast(callback, c.c_void_p).value for callback in self.callbacks))
        self.instance = (c.c_void_p * 1)(c.addressof(self.table))
        self.address = c.addressof(self.instance)
        self.drop_owner_reference = lambda: drop(self.address)
        _handlers[self.address] = self

    def take_client(self):
        with self.lock:
            client, self.client = self.client, c.c_void_p()
            return client

    def close(self):
        with self.lock:
            if self.abandoned:
                return
            self.abandoned = True
            release(self.client)
            self.client = c.c_void_p()
            self.drop_owner_reference()


class ProcessCapture:
    channels = 2

    def __init__(self, pid, include_tree=True):
        ensure_supported()
        self.pid = pid
        self.include_tree = include_tree
        self.client = c.c_void_p()
        self.capture = c.c_void_p()
        self.operation = c.c_void_p()
        self.event = None
        self.pending = np.empty((0, 2), dtype=np.float32)
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateEventW.argtypes = [c.c_void_p, c.c_int, c.c_int, c.c_wchar_p]
        self.kernel.CreateEventW.restype = c.c_void_p
        self.kernel.WaitForSingleObject.argtypes = [c.c_void_p, c.c_uint32]
        self.kernel.CloseHandle.argtypes = [c.c_void_p]

    def __enter__(self):
        try:
            parameters = ActivationParameters(1, self.pid, 0 if self.include_tree else 1)
            variant = PropVariant()
            variant.vt = 65  # VT_BLOB
            variant.payload.blob = Blob(c.sizeof(parameters), c.addressof(parameters))
            self.handler = CompletionHandler()
            self.handler.activation_data = (parameters, variant)
            dll = c.WinDLL('mmdevapi')
            dll.ActivateAudioInterfaceAsync.argtypes = [c.c_wchar_p, c.POINTER(GUID), c.POINTER(PropVariant), c.c_void_p, c.POINTER(c.c_void_p)]
            check(dll.ActivateAudioInterfaceAsync('VAD\\Process_Loopback', c.byref(IAUDIOCLIENT), c.byref(variant), self.handler.address, c.byref(self.operation)))
            if not self.handler.done.wait(10):
                raise TimeoutError('Windows process capture activation timed out.')
            if self.handler.error:
                raise self.handler.error
            self.client = self.handler.take_client()
            format = WaveFormat(3, 2, 48000, 384000, 8, 32, 0)
            flags = 0x00020000 | 0x00040000 | 0x80000000
            call(self.client, 3, [c.c_int, c.c_uint32, c.c_int64, c.c_int64, c.POINTER(WaveFormat), c.c_void_p],
                 0, flags, 0, 0, c.byref(format), None)
            self.event = self.kernel.CreateEventW(None, False, False, None)
            if not self.event:
                raise c.WinError(c.get_last_error())
            call(self.client, 13, [c.c_void_p], self.event)
            call(self.client, 14, [c.POINTER(GUID), c.POINTER(c.c_void_p)], c.byref(IAUDIOCAPTURECLIENT), c.byref(self.capture))
            call(self.client, 10, [])
            return self
        except Exception:
            self.close()
            raise

    def record(self, numframes=960):
        deadline = time.monotonic() + .1
        while len(self.pending) < numframes:
            available = c.c_uint32()
            call(self.capture, 5, [c.POINTER(c.c_uint32)], c.byref(available))
            if available.value:
                pointer, frames, flags = c.c_void_p(), c.c_uint32(), c.c_uint32()
                position, timestamp = c.c_uint64(), c.c_uint64()
                call(self.capture, 3, [c.POINTER(c.c_void_p), c.POINTER(c.c_uint32), c.POINTER(c.c_uint32),
                                      c.POINTER(c.c_uint64), c.POINTER(c.c_uint64)],
                     c.byref(pointer), c.byref(frames), c.byref(flags), c.byref(position), c.byref(timestamp))
                try:
                    data = np.zeros((frames.value, 2), dtype=np.float32) if flags.value & 2 else np.ctypeslib.as_array(
                        c.cast(pointer, c.POINTER(c.c_float)), shape=(frames.value * 2,)).reshape(-1, 2).copy()
                    self.pending = np.concatenate((self.pending, data))
                finally:
                    call(self.capture, 4, [c.c_uint32], frames.value)
            elif time.monotonic() >= deadline:
                self.pending = np.pad(self.pending, ((0, numframes - len(self.pending)), (0, 0)))
                break
            else:
                self.kernel.WaitForSingleObject(self.event, 20)
        result, self.pending = self.pending[:numframes], self.pending[numframes:]
        return result

    def close(self):
        if self.client:
            try:
                call(self.client, 11, [])
            except OSError:
                pass
        release(self.capture)
        release(self.client)
        release(self.operation)
        self.capture, self.client, self.operation = c.c_void_p(), c.c_void_p(), c.c_void_p()
        if hasattr(self, 'handler'):
            self.handler.close()
        if self.event:
            self.kernel.CloseHandle(self.event)
            self.event = None

    def __exit__(self, *args):
        self.close()

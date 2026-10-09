"""Windows per-process endpoint preferences (internal, version-dependent API)."""
import ctypes as c
from comtypes import GUID


class Routing:
    PREFIX = "\\\\?\\SWD#MMDEVAPI#"
    SUFFIX = ("#{e6327cad-dcec-4949-ae8a-991e976a79d2}",
              "#{2eef81be-33fa-4800-9670-1cd474972c3f}")

    def __init__(self):
        self.dll = c.WinDLL("combase")
        self.dll.WindowsCreateString.argtypes = [c.c_wchar_p, c.c_uint32, c.POINTER(c.c_void_p)]
        self.dll.WindowsDeleteString.argtypes = [c.c_void_p]
        self.dll.WindowsGetStringRawBuffer.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
        self.dll.WindowsGetStringRawBuffer.restype = c.c_wchar_p
        self.dll.RoGetActivationFactory.argtypes = [c.c_void_p, c.POINTER(GUID), c.POINTER(c.c_void_p)]
        self.ptr = c.c_void_p()
        name = self._string("Windows.Media.Internal.AudioPolicyConfig")
        try:
            for iid in ("ab3d4648-e242-459f-b02f-541c70306324", "2a59116d-6c4f-45e0-a74f-707e3fef9258"):
                hr = self.dll.RoGetActivationFactory(name, c.byref(GUID("{" + iid + "}")), c.byref(self.ptr))
                if hr >= 0:
                    break
            self._check(hr)
        finally:
            self.dll.WindowsDeleteString(name)

    @staticmethod
    def _check(hr):
        if hr < 0:
            raise OSError(f"Windows audio routing failed (0x{hr & 0xffffffff:08X}).")

    def _string(self, value):
        ptr = c.c_void_p()
        self._check(self.dll.WindowsCreateString(value, len(value), c.byref(ptr)))
        return ptr

    def _call(self, slot, args, *values):
        vtable = c.cast(self.ptr, c.POINTER(c.POINTER(c.c_void_p))).contents
        method = c.WINFUNCTYPE(c.c_int32, c.c_void_p, *args)(vtable[slot])
        self._check(method(self.ptr, *values))

    def get(self, pid, flow=0, role=1):
        result = c.c_void_p()
        self._call(26, [c.c_uint32, c.c_int, c.c_int, c.POINTER(c.c_void_p)], pid, flow, role, c.byref(result))
        try:
            value = self.dll.WindowsGetStringRawBuffer(result, None) if result else ""
            return (value or "").removeprefix(self.PREFIX).removesuffix(self.SUFFIX[flow])
        finally:
            if result:
                self.dll.WindowsDeleteString(result)

    def snapshot(self, pid, flow=0):
        return tuple(self.get(pid, flow, role) for role in range(3))

    def set(self, pid, device_id, flow=0):
        """Set all three roles; restore already changed roles on failure."""
        previous = self.snapshot(pid, flow)
        targets = device_id if isinstance(device_id, tuple) else (device_id,) * 3
        if len(targets) != 3:
            raise ValueError("A route snapshot must contain three role preferences.")
        strings = []
        def endpoint_string(value):
            ptr = self._string(self.PREFIX + value + self.SUFFIX[flow]) if value else c.c_void_p()
            strings.append(ptr)
            return ptr
        changed = []
        try:
            new_strings = [endpoint_string(value) for value in targets]
            old_strings = [endpoint_string(value) for value in previous]
            for role in (0, 1, 2):
                self._call(25, [c.c_uint32, c.c_int, c.c_int, c.c_void_p], pid, flow, role, new_strings[role])
                changed.append(role)
        except Exception:
            for role in changed:
                self._call(25, [c.c_uint32, c.c_int, c.c_int, c.c_void_p], pid, flow, role, old_strings[role])
            raise
        finally:
            for ptr in strings:
                if ptr:
                    self.dll.WindowsDeleteString(ptr)

    def close(self):
        if self.ptr:
            vtable = c.cast(self.ptr, c.POINTER(c.POINTER(c.c_void_p))).contents
            c.WINFUNCTYPE(c.c_ulong, c.c_void_p)(vtable[2])(self.ptr)
            self.ptr = c.c_void_p()

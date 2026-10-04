"""Throwaway: raw DeviceIoControl against \\\\.\\interceptionNN to see the driver's own error codes."""
import ctypes
import ctypes.wintypes as w

kernel32 = ctypes.windll.kernel32
kernel32.CreateFileW.restype = w.HANDLE
kernel32.DeviceIoControl.argtypes = [w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.c_void_p, w.DWORD,
                                     ctypes.POINTER(w.DWORD), ctypes.c_void_p]
IOCTL_GET_HARDWARE_ID = 0x222200
IOCTL_GET_PRECEDENCE = 0x222108
IOCTL_GET_FILTER = 0x222020

for i in (0, 1, 10, 11):
    h = kernel32.CreateFileW(f"\\\\.\\interception{i:02d}", 0x80000000 | 0x40000000, 0, None, 3, 0, None)
    for name, code in (("hwid", IOCTL_GET_HARDWARE_ID), ("precedence", IOCTL_GET_PRECEDENCE), ("filter", IOCTL_GET_FILTER)):
        buf = ctypes.create_string_buffer(1024)
        got = w.DWORD(0)
        ctypes.windll.kernel32.SetLastError(0)
        ok = kernel32.DeviceIoControl(h, code, None, 0, buf, 1024, ctypes.byref(got), None)
        print(f"interception{i:02d} {name}: ok={ok} bytes={got.value} err={ctypes.GetLastError()} "
              f"data={buf.raw[:got.value][:80]!r}")
    kernel32.CloseHandle(h)

"""Throwaway diagnostics: can the Interception driver see any keyboard/mouse devices?"""
import ctypes
import ctypes.wintypes as w

kernel32 = ctypes.windll.kernel32
kernel32.CreateFileW.restype = w.HANDLE
lib = ctypes.CDLL(r"D:\MyClicker\Interception\Interception\library\x64\interception.dll")
lib.interception_create_context.restype = ctypes.c_void_p
lib.interception_get_hardware_id.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
lib.interception_get_hardware_id.restype = ctypes.c_uint
lib.interception_get_filter.argtypes = [ctypes.c_void_p, ctypes.c_int]

for i in range(20):
    h = kernel32.CreateFileW(f"\\\\.\\interception{i:02d}", 0x80000000, 0, None, 3, 0, None)
    err = ctypes.GetLastError()
    ok = h not in (None, w.HANDLE(-1).value, -1)
    print(f"interception{i:02d}: open={ok} err={err}")
    if ok:
        kernel32.CloseHandle(h)

ctx = lib.interception_create_context()
print("context:", hex(ctx or 0))
for device in range(1, 21):
    buf = ctypes.create_string_buffer(1024)
    n = lib.interception_get_hardware_id(ctx, device, buf, 1024)
    hwid = buf.raw[:n].decode("utf-16-le", "replace").replace("\0", " | ") if n else ""
    print(f"device {device:2d}: bytes={n} filter={lib.interception_get_filter(ctx, device)} {hwid}")

"""Throwaway: restart the touchpad mouse device so upper filters (Interception) re-attach, then re-run diagnostics."""
import subprocess
import time

r = subprocess.run(["pnputil", "/restart-device", r"HID\ELAN1205&COL01\5&4D8DF7&0&0000"], capture_output=True)
print(r.returncode, r.stdout.decode("cp866", "replace"), r.stderr.decode("cp866", "replace"))
time.sleep(3)
import interception_diag  # noqa: E402,F401  (prints device table)

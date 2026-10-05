"""Build MyClicker.exe into the repository root: `python build.py`.

Runs the test suite first and refuses to build on a failure. The exe asks for administrator rights itself
(UAC manifest) and, being portable, keeps its data in data/ next to itself — the same folder `run.py` uses.
Needs PyInstaller: `python -m pip install pyinstaller`.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=ROOT)
    if tests.returncode != 0:
        print("Tests failed — exe not built.")
        return tests.returncode
    import PyInstaller.__main__
    PyInstaller.__main__.run([
        str(ROOT / "run.py"),
        "--name", "MyClicker",
        "--onefile",
        "--windowed",            # no console window
        "--uac-admin",           # games run elevated; input from a non-elevated process is blocked (UIPI)
        "--distpath", str(ROOT),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--clean",
        "--noconfirm",
    ])
    print(f"Built {ROOT / 'MyClicker.exe'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

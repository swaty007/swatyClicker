"""Elevated runner, launched by the scheduled task MyClicker-Probe.

Reads probe/job.json -> {"script": "<file in probe/>", "args": [...]} and runs it,
writing combined output to probe/results/last_run.txt. Only scripts that live
in the probe folder are allowed.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)
out_path = os.path.join(RESULTS, "last_run.txt")

with open(out_path, "w", encoding="utf-8") as out:
    try:
        job = json.load(open(os.path.join(HERE, "job.json"), encoding="utf-8-sig"))
        script = os.path.abspath(os.path.join(HERE, job["script"]))
        if os.path.dirname(script) != HERE:
            raise ValueError("script must live in the probe folder")
        python = sys.executable.replace("pythonw.exe", "python.exe")
        proc = subprocess.run([python, script, *job.get("args", [])], cwd=HERE,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              creationflags=0x08000000, timeout=600)
        out.write(proc.stdout.decode("utf-8", "replace"))
        out.write(f"\nEXIT {proc.returncode}\n")
    except Exception as e:
        out.write(f"RUNNER ERROR {e!r}\nEXIT -1\n")


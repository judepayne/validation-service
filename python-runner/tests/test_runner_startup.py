#!/usr/bin/env python3
"""Quick test to see runner startup errors"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subprocess
import time

_RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
proc = subprocess.Popen(
    ['python3', os.path.join(_RUNNER_DIR, 'runner.py'), os.path.join(_RUNNER_DIR, 'config.yaml')],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

print("Process started, PID:", proc.pid)
time.sleep(0.5)

# Check if process is still running
poll = proc.poll()
if poll is not None:
    print(f"Process exited with code: {poll}")
    stderr = proc.stderr.read().decode()
    stdout = proc.stdout.read().decode()
    print("STDERR:")
    print(stderr)
    print("\nSTDOUT:")
    print(stdout)
else:
    print("Process still running")
    proc.terminate()
    proc.wait()

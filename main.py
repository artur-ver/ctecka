#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import os

# Paths to the scripts
script_dir = os.path.dirname(os.path.realpath(__file__))
app_draha1_path = os.path.join(script_dir, 'app_draha1.py')
app_draha2_path = os.path.join(script_dir, 'app_draha2.py')

def run_script(script_path):
    """Run a Python script as a subprocess."""
    try:
        subprocess.run([sys.executable, script_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_path}: {e}")
    except KeyboardInterrupt:
        print(f"Interrupted {script_path}")

if __name__ == "__main__":
    # Run both scripts in parallel using subprocess
    # Since they are infinite loops, we need to run them in background
    proc1 = subprocess.Popen([sys.executable, app_draha1_path])
    proc2 = subprocess.Popen([sys.executable, app_draha2_path])

    # Wait for both to finish (though they won't since infinite loops)
    try:
        proc1.wait()
        proc2.wait()
    except KeyboardInterrupt:
        print("Stopping processes...")
        proc1.terminate()
        proc2.terminate()
        proc1.wait()
        proc2.wait()
        print("Processes stopped.")
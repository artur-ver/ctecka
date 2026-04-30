#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import os
from datetime import datetime

from system_utils import request_reboot

# Reboot window: 02:00 – 03:00
START_HOUR = 2
END_HOUR = 3

CHECK_INTERVAL = 60 * 60  # check every hour

BASE_DIR = os.path.dirname(__file__)
FLAG_FILE = os.path.join(BASE_DIR, "last_reboot_date.txt")
LOG_RESTART_FILE = os.path.join(BASE_DIR, "log_restart.txt")


def reboot_allowed():
    now = datetime.now()
    if not (START_HOUR <= now.hour < END_HOUR):
        return False
    today = now.strftime("%Y-%m-%d")
    if os.path.exists(FLAG_FILE):
        with open(FLAG_FILE, "r") as f:
            if f.readline().strip() == today:
                return False  # already rebooted today
    return True


def mark_reboot():
    today = datetime.now().strftime("%Y-%m-%d")
    tmp = FLAG_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(today + "\n")
    os.replace(tmp, FLAG_FILE)
    print(f"[restart.py] Wrote flag file: {FLAG_FILE}")


def clear_reboot_mark():
    if os.path.exists(FLAG_FILE):
        os.remove(FLAG_FILE)
        print(f"[restart.py] Removed flag file: {FLAG_FILE}")


def log_restart(event):
    message = f"{datetime.now():%Y-%m-%d %H:%M:%S.%f} - raspberry {event}"
    with open(LOG_RESTART_FILE, "a") as f:
        f.write(message + "\n")


def tail(file_path, lines=30):
    with open(file_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        size = 1024
        data = b""
        while end > 0 and data.count(b"\n") < lines + 1:
            start = max(0, end - size)
            f.seek(start)
            data = f.read(end - start) + data
            end = start
            size *= 2
        return b"\n".join(data.splitlines()[-lines:]).decode(errors="replace")


if __name__ == "__main__":
    log_restart("start")
    while True:
        if os.path.exists(LOG_RESTART_FILE):
            print(tail(LOG_RESTART_FILE, 30))
        print("restart.py running")
        if reboot_allowed():
            mark_reboot()
            log_restart("off")
            success, message = request_reboot()
            if success:
                break

            clear_reboot_mark()
            log_restart(f"reboot failed: {message}")
            print(f"[restart.py] reboot command failed: {message}")
        time.sleep(CHECK_INTERVAL)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
LOG_DIR_ROOT = os.path.join(SCRIPT_DIR, 'logs')
NSENT_DIR = os.path.join(LOG_DIR_ROOT, 'nsent')

CHECK_INTERVAL = 120        # seconds between health checks (2 min)
MAX_LOG_GAP_MINUTES = 6     # restart if no new log for this many minutes

# A log is considered "small" (likely empty / error) below this byte count
MAX_SMALL_LOG_SIZE = 1000
MAX_CONSECUTIVE_SMALL = 3   # restart after this many consecutive small logs

COUNTER_FILE = os.path.join(SCRIPT_DIR, 'restart_counter.txt')
MAX_RESTARTS_PER_DAY = 2


def get_today():
    return datetime.now().strftime('%Y-%m-%d')


def load_restart_counter():
    if not os.path.exists(COUNTER_FILE):
        return get_today(), 0
    with open(COUNTER_FILE, 'r') as f:
        line = f.read().strip()
    try:
        date_str, count = line.split(',')
        if date_str != get_today():
            return get_today(), 0
        return date_str, int(count)
    except Exception:
        return get_today(), 0


def save_restart_counter(date_str, count):
    with open(COUNTER_FILE, 'w') as f:
        f.write(f"{date_str},{count}")


def get_sorted_logs_by_ctime(log_dir):
    """Return list of (filename, ctime, size) tuples sorted by ctime."""
    if not os.path.isdir(log_dir):
        return []
    logs = [f for f in os.listdir(log_dir) if f.endswith('.log')]
    logs = [
        (f,
         os.path.getctime(os.path.join(log_dir, f)),
         os.path.getsize(os.path.join(log_dir, f)))
        for f in logs
    ]
    logs.sort(key=lambda x: x[1])
    return logs


def check_log_problem():
    """
    Return True if the QR scanner app appears stuck:
    - Three or more consecutive log files are suspiciously small, OR
    - The newest log file is older than MAX_LOG_GAP_MINUTES minutes.
    """
    today_dir = os.path.join(LOG_DIR_ROOT, get_today())
    logs = get_sorted_logs_by_ctime(today_dir) + get_sorted_logs_by_ctime(NSENT_DIR)

    if not logs:
        return False

    # Check for consecutive small logs
    consecutive_small = 0
    for _, _, size in logs[-MAX_CONSECUTIVE_SMALL:]:
        if size <= MAX_SMALL_LOG_SIZE:
            consecutive_small += 1
        else:
            consecutive_small = 0

    if consecutive_small >= MAX_CONSECUTIVE_SMALL:
        print("[monitor] too many consecutive small logs — problem detected")
        return True

    # Check for log gap
    last_ctime = logs[-1][1]
    gap_min = (time.time() - last_ctime) / 60
    if gap_min > MAX_LOG_GAP_MINUTES:
        print(f"[monitor] no new log for {gap_min:.1f} min — problem detected")
        return True

    return False


def reboot_raspberry():
    date_str, count = load_restart_counter()
    if count >= MAX_RESTARTS_PER_DAY:
        print("[monitor] restart limit reached for today, not rebooting")
        return
    count += 1
    save_restart_counter(date_str, count)
    print(f"[monitor] rebooting raspberry ({count}/{MAX_RESTARTS_PER_DAY})")
    os.system("sudo reboot")


def main():
    print("[monitor] start")
    while True:
        if check_log_problem():
            reboot_raspberry()
            time.sleep(300)  # wait 5 min after reboot trigger before next check
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()

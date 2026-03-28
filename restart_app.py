import os
import time
from datetime import datetime
import sys

from config import CISLO_DRAHY, CISLO_DRAHY2, LOG_DIR_ROOT

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
NSENT_DIR = os.path.join(LOG_DIR_ROOT, 'nsent')

CHECK_INTERVAL = 120  # 2 min
MAX_LOG_GAP_MINUTES = 6

MAX_SMALL_LOG_SIZE = 1000
MAX_CONSECUTIVE_SMALL = 3

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
    except:
        return get_today(), 0


def save_restart_counter(date_str, count):
    with open(COUNTER_FILE, 'w') as f:
        f.write(f"{date_str},{count}")


def get_sorted_logs_by_ctime(log_dir):
    if not os.path.isdir(log_dir):
        return []
    logs = [f for f in os.listdir(log_dir) if f.endswith('.log')]
    logs = [(f, os.path.getctime(os.path.join(log_dir, f)),
             os.path.getsize(os.path.join(log_dir, f))) for f in logs]
    logs.sort(key=lambda x: x[1])
    return logs

def get_sorted_logs_by_ctime_filtered(log_dir, prefix):
    if not os.path.isdir(log_dir):
        return []
    logs = [f for f in os.listdir(log_dir) if f.endswith('.log') and f.startswith(prefix)]
    logs = [(f, os.path.getctime(os.path.join(log_dir, f)),
             os.path.getsize(os.path.join(log_dir, f))) for f in logs]
    logs.sort(key=lambda x: x[1])
    return logs

def track_has_problem(track_code):
    today_dir = os.path.join(LOG_DIR_ROOT, get_today())
    prefix = "carkod_{}_".format(track_code)

    logs = get_sorted_logs_by_ctime_filtered(today_dir, prefix) + get_sorted_logs_by_ctime_filtered(NSENT_DIR, prefix)
    if not logs:
        return True

    consecutive_small = 0
    for _, _, size in logs[-MAX_CONSECUTIVE_SMALL:]:
        if size <= MAX_SMALL_LOG_SIZE:
            consecutive_small += 1
        else:
            consecutive_small = 0

    if consecutive_small >= MAX_CONSECUTIVE_SMALL:
        return True

    last_log = logs[-1]
    gap_min = (time.time() - last_log[1]) / 60
    return gap_min > MAX_LOG_GAP_MINUTES


def check_log_problem():
    if track_has_problem(CISLO_DRAHY):
        return True
    if track_has_problem(CISLO_DRAHY2):
        return True
    return False


def reboot_raspberry():
    date_str, count = load_restart_counter()

    if count >= MAX_RESTARTS_PER_DAY:
        print("[monitor] restart limit reached for today")
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
            time.sleep(300)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(f"[monitor] error: {e}")
            time.sleep(10)


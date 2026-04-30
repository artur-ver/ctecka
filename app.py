#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import signal
import serial
import time
import shutil
import os
from multiprocessing import Process
import subprocess
from datetime import datetime
from os import path as os_path
from pathlib import Path

from send import upload_file_to_ftp_server
from config import (
    FTP_HOST, FTP_USER, FTP_PASS,
    LOG_DIR_ROOT,
    USB_DEVICE_1, USB_DEVICE_2,
    FILE_PREFIX_1, FILE_PREFIX_2,
    BAUD_RATE, TIMEOUT, LOG_TIME, TIME_FORMAT,
    LOG_TYPE_LOG, LOG_TYPE_INFO, LOG_TYPE_ERROR,
)

####################################################################


class KillWatcher:
    """Catch SIGINT / SIGTERM so each process can stop cleanly."""
    stopLoop = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.stopLoop = True


# ── helpers ──────────────────────────────────────────────────────────────────

def new_logfile_name(prefix):
    return prefix + "_" + datetime.now().strftime(TIME_FORMAT) + ".log"


def new_logpath_nsent(log_file):
    """Return path inside logs/nsent/ (for files not yet sent to FTP)."""
    nsent_dir = os_path.join(LOG_DIR_ROOT, "nsent")
    Path(nsent_dir).mkdir(parents=True, exist_ok=True)
    return os_path.join(nsent_dir, log_file)


def move_log_to_date_folder(log_file_path, log_file_name):
    """Move a log file to logs/YYYY-MM-DD/ after successful FTP upload."""
    dated_dir = os_path.join(LOG_DIR_ROOT, datetime.now().strftime("%Y-%m-%d"))
    Path(dated_dir).mkdir(parents=True, exist_ok=True)
    new_path = os_path.join(dated_dir, log_file_name)
    shutil.move(log_file_path, new_path)
    return new_path


def time_now():
    return datetime.now().strftime("%Y-%m-%d_%H:%M:%S.%f")[:-3]


def log_print(data, log_type=LOG_TYPE_LOG, loc=None):
    """Append one line to the current log file."""
    try:
        with open(loc, "a", encoding="UTF-8") as f:
            f.write(f"[{log_type}]\t{time_now()}\t'{data}'\n")
    except Exception as e:
        print(f"[log_print error] {e}")


def stamp(minutes=0):
    """Monotonic timestamp in nanoseconds, optionally offset by N minutes."""
    return time.monotonic_ns() + (minutes * 60 * 1_000_000_000)


# ── unsent-log recovery ───────────────────────────────────────────────────────

def is_not_sended_empty():
    not_sended_root = os_path.join(LOG_DIR_ROOT, "not_sended_data")
    if not os.path.exists(not_sended_root):
        return True
    return not any(f.endswith(".log") for f in os.listdir(not_sended_root))


def try_resend_not_sended():
    """Re-upload any files sitting in logs/not_sended_data/, oldest first."""
    not_sended_root = os_path.join(LOG_DIR_ROOT, "not_sended_data")
    if not os.path.exists(not_sended_root):
        return
    files = sorted(f for f in os.listdir(not_sended_root) if f.endswith(".log"))
    for file in files:
        file_path = os_path.join(not_sended_root, file)
        try:
            upload_file_to_ftp_server(file_path, FTP_HOST, FTP_USER, FTP_PASS)
            archive_dir = os_path.join(LOG_DIR_ROOT, "archive")
            Path(archive_dir).mkdir(parents=True, exist_ok=True)
            shutil.move(file_path, os_path.join(archive_dir, os.path.basename(file_path)))
        except Exception as e:
            print(f"[resend] failed for {file}: {e}")
            break  # stop if current file cannot be sent


def try_send_all_nsent_and_write_txt():
    """Send every file in logs/nsent/ to FTP, then move to dated folder."""
    nsent_dir = os_path.join(LOG_DIR_ROOT, "nsent")
    if not os.path.exists(nsent_dir):
        return
    sent_files = []
    files = sorted(f for f in os.listdir(nsent_dir) if f.endswith(".log"))
    for file in files:
        file_path = os_path.join(nsent_dir, file)
        try:
            upload_file_to_ftp_server(file_path, FTP_HOST, FTP_USER, FTP_PASS)
            move_log_to_date_folder(file_path, file)
            print(f"[nsent->date] Sent and moved: {file}")
            sent_files.append(file)
        except Exception as e:
            print(f"[nsent->date] Not sent: {file} ({e})")
            break  # stop on first failure

    if sent_files:
        nsent_txt = os_path.join(os_path.dirname(__file__), "nsent_logs.txt")
        with open(nsent_txt, "w") as f:
            for fname in sent_files:
                f.write(fname + "\n")


# ── scanner worker ────────────────────────────────────────────────────────────

def scanner_loop(device, prefix):
    """
    Worker process for one QR scanner.

    Opens the USB serial port, reads QR-code lines, writes them to a log
    file in logs/nsent/, and uploads to FTP every LOG_TIME minutes.
    Unsent logs from previous cycles are retried at the start of each cycle.
    """
    LOOP = KillWatcher()

    try:
        ser = serial.Serial(device, BAUD_RATE, timeout=0)
        print(f"[{prefix}] Opened {device} @ {BAUD_RATE} baud")
    except Exception as e:
        print(f"[{prefix}] Cannot open {device}: {e}")
        return

    while not LOOP.stopLoop:
        # --- retry previously unsent logs ---
        if not is_not_sended_empty():
            try:
                try_resend_not_sended()
            except Exception as e:
                print(f"[{prefix}] Resend error: {e}")

        # --- open new log file in nsent/ ---
        log_file = new_logfile_name(prefix)
        log_path = new_logpath_nsent(log_file)
        log_print("Starting new log session", LOG_TYPE_INFO, log_path)

        next_log = stamp(LOG_TIME)

        # --- read QR codes until next rotation time ---
        while not LOOP.stopLoop:
            try:
                raw = ser.readline().rstrip()
                if raw:
                    decoded = raw.decode("utf-8", errors="replace").strip()
                    if decoded:
                        print(f"[{prefix}] {time_now()} - [{decoded}]")
                        log_print(decoded, LOG_TYPE_LOG, log_path)
            except Exception as e:
                log_print(str(e), LOG_TYPE_ERROR, log_path)

            time.sleep(TIMEOUT)

            if next_log < stamp():
                break

        log_print("End of log session", LOG_TYPE_INFO, log_path)

        # --- upload current log to FTP ---
        try:
            upload_file_to_ftp_server(log_path, FTP_HOST, FTP_USER, FTP_PASS)
            move_log_to_date_folder(log_path, log_file)
            print(f"[{prefix}] Sent: {log_file} @ {time_now()}")

            # spawn process to flush the rest of nsent/
            p = Process(target=try_send_all_nsent_and_write_txt)
            p.start()

            # launch ftp_size_control to verify upload integrity
            subprocess.Popen(
                ["python3", os_path.join(os_path.dirname(__file__), "ftp_size_control.py")]
            )
        except Exception as e:
            log_print(f"Upload error: {e}", LOG_TYPE_ERROR, log_path)

    print(f"[{prefix}] Stopping.")
    ser.close()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting QR scanner app — two devices in parallel")

    p1 = Process(target=scanner_loop, args=(USB_DEVICE_1, FILE_PREFIX_1))
    p2 = Process(target=scanner_loop, args=(USB_DEVICE_2, FILE_PREFIX_2))

    p1.start()
    p2.start()

    p1.join()
    p2.join()

    print("QR scanner app stopped.")

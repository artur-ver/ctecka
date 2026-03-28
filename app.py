#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import signal
import shutil
import subprocess
import sys
import time
from datetime import datetime
from multiprocessing import Process
from os import path as os_path
from pathlib import Path

import serial

from config import CISLO_DRAHY, FTP_HOST, FTP_PASS, FTP_USER, LOG_DIR_ROOT, LOG_TIME, LOG_TYPE_ERROR, LOG_TYPE_INFO, LOG_TYPE_LOG, SERIAL_DEVICE, TIMEOUT, TIME_FORMAT
from send import upload_file_to_ftp_server

####################################################################

SERIAL_COMMANDS = [b'V\n', b'X,1\n']

####################################################################


class KillWatcher:
    stopLoop = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
    def exit_gracefully(self, *args):
        self.stopLoop = True


def new_logfile_name(track_code):
    return "carkod_{}_{}.log".format(track_code, datetime.now().strftime(TIME_FORMAT))


def new_logpath(log_file):
    LOG_DIR = os_path.join(LOG_DIR_ROOT, datetime.now().strftime("%Y-%m-%d"))
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    return os_path.join(LOG_DIR, log_file)


def new_logpath_nsent(log_file):
    nsent_dir = os_path.join(LOG_DIR_ROOT, "nsent")
    Path(nsent_dir).mkdir(parents=True, exist_ok=True)
    return os_path.join(nsent_dir, log_file)


def time_now():
    return datetime.now().strftime("%Y-%m-%d_%H:%M:%S.%f")[:-3]


def log_print(data, type=LOG_TYPE_LOG, loc=None):
    try:
        with open(loc, "a", encoding="UTF-8") as log_f:
            log_f.write(f"[{type}]\t{time_now()}\t'{data}'\n")
    except Exception as e:
        print(f"Log write error: {e}")


def stamp(minutes=0):
    return time.monotonic_ns() + (minutes * 60 * 1000000000)


def move_log_to_date_folder(log_file_path, log_file_name):
    dated_dir = os_path.join(LOG_DIR_ROOT, datetime.now().strftime("%Y-%m-%d"))
    Path(dated_dir).mkdir(parents=True, exist_ok=True)
    new_path = os_path.join(dated_dir, log_file_name)
    shutil.move(log_file_path, new_path)
    return new_path


def get_nsent_txt_path(track_code):
    if track_code:
        return os.path.join(os.path.dirname(__file__), "nsent_logs_{}.txt".format(track_code))
    return os.path.join(os.path.dirname(__file__), "nsent_logs.txt")


def iter_nsent_files(track_code):
    nsent_dir = os_path.join(LOG_DIR_ROOT, "nsent")
    if not os.path.exists(nsent_dir):
        return []
    prefix = "carkod_{}_".format(track_code) if track_code else ""
    files = [f for f in os.listdir(nsent_dir) if f.endswith(".log")]
    if prefix:
        files = [f for f in files if f.startswith(prefix)]
    files.sort()
    return [os_path.join(nsent_dir, f) for f in files]


def try_resend_not_sended(track_code):
    files = iter_nsent_files(track_code)
    if not files:
        return
    for file_path in files:
        try:
            upload_file_to_ftp_server(file_path, FTP_HOST, FTP_USER, FTP_PASS)
            move_log_to_date_folder(file_path, os.path.basename(file_path))
        except Exception as e:
            log_print(f"Resend failed: {e}", LOG_TYPE_ERROR, file_path)
            break


def is_not_sended_empty(track_code):
    return len(iter_nsent_files(track_code)) == 0


def try_send_all_nsent_and_write_txt(track_code):
    sent_files = []
    for file_path in iter_nsent_files(track_code):
        try:
            upload_file_to_ftp_server(file_path, FTP_HOST, FTP_USER, FTP_PASS)
            filename = os.path.basename(file_path)
            move_log_to_date_folder(file_path, filename)
            print(f"[nsent->date] Sent and moved: {filename}")
            sent_files.append(filename)
        except Exception as e:
            print(f"[nsent->date] Not sent: {os.path.basename(file_path)} ({e})")
            break

    if sent_files:
        nsent_txt = get_nsent_txt_path(track_code)
        with open(nsent_txt, "w") as f:
            for fname in sent_files:
                f.write(fname + "\n")


def main_loop(serial_device=SERIAL_DEVICE, track_code=CISLO_DRAHY):
    LOOP = KillWatcher()
    ser = serial.Serial(serial_device, 115200, timeout=0)
    print("Flush at start")
    ser.flush()
    print(b'X,0\r\n')
    ser.write(b'X,0\r\n')
    print("#####################")
    print(b'V\n')
    ser.write(b'V\n')
    print(b'X,1\n')
    ser.write(b'X,1\r\n')

    while not LOOP.stopLoop:
        next_log = stamp(LOG_TIME)
        if not is_not_sended_empty(track_code):
            try:
                try_resend_not_sended(track_code)
            except Exception as e:
                log_print(f"Resend error: {e}", LOG_TYPE_ERROR)

        log_file = new_logfile_name(track_code)
        log_path = new_logpath_nsent(log_file)
        log_print("Starting new log session", LOG_TYPE_INFO, log_path)
        while not LOOP.stopLoop:
            try:
                readOut = ser.readline().rstrip()
                if readOut:
                    print(f"\t {time_now()} - [{readOut}]")
                    log_print(readOut, LOG_TYPE_LOG, log_path)
            except Exception as e:
                log_print(e, LOG_TYPE_ERROR, log_path)
            time.sleep(TIMEOUT)
            if next_log < stamp():
                break

        log_print("End of log session", LOG_TYPE_INFO, log_path)

        try:
            try:
                upload_file_to_ftp_server(log_path, FTP_HOST, FTP_USER, FTP_PASS)
                move_log_to_date_folder(log_path, log_file)
                print(f"Sending: {log_file} @{time_now()}")

                p = Process(target=try_send_all_nsent_and_write_txt, args=(track_code,))
                p.start()

                subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "ftp_size_control.py"), "--nsent-file", get_nsent_txt_path(track_code)])

            except Exception as e:
                log_print(f"Upload error: {e}", LOG_TYPE_ERROR, log_path)
        except Exception as e:
            log_print(f"Unexpected main loop error: {e}", LOG_TYPE_ERROR, log_path)

    print("Stopping APP.")
    print("Flush")
    ser.flush()
    print(b'X,0\r\n')
    ser.write(b'X,0\r\n')


if __name__ == "__main__":
    while True:
        try:
            main_loop()
        except Exception as e:
            print(f"Fatal error: {e}")

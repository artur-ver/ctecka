#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import signal
import serial
import time
import shutil
import os
import select
import struct
from multiprocessing import Process
import subprocess
from datetime import datetime
from glob import glob
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

INPUT_EVENT_STRUCT = struct.Struct("llHHi")
EV_KEY = 0x01
ENTER_KEYS = {28, 96}
SHIFT_KEYS = {42, 54}
ALT_KEYS = {56, 100}

ALT_DIGIT_KEYMAP = {
    2: "1",
    3: "2",
    4: "3",
    5: "4",
    6: "5",
    7: "6",
    8: "7",
    9: "8",
    10: "9",
    11: "0",
    71: "7",
    72: "8",
    73: "9",
    75: "4",
    76: "5",
    77: "6",
    79: "1",
    80: "2",
    81: "3",
    82: "0",
}

SHIFTED_DIGIT_TO_DIGIT = {
    ")": "0",
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
}

HID_KEYMAP = {
    2: ("1", "!"),
    3: ("2", "@"),
    4: ("3", "#"),
    5: ("4", "$"),
    6: ("5", "%"),
    7: ("6", "^"),
    8: ("7", "&"),
    9: ("8", "*"),
    10: ("9", "("),
    11: ("0", ")"),
    12: ("-", "_"),
    13: ("=", "+"),
    15: ("\t", "\t"),
    16: ("q", "Q"),
    17: ("w", "W"),
    18: ("e", "E"),
    19: ("r", "R"),
    20: ("t", "T"),
    21: ("y", "Y"),
    22: ("u", "U"),
    23: ("i", "I"),
    24: ("o", "O"),
    25: ("p", "P"),
    26: ("[", "{"),
    27: ("]", "}"),
    28: ("\n", "\n"),
    30: ("a", "A"),
    31: ("s", "S"),
    32: ("d", "D"),
    33: ("f", "F"),
    34: ("g", "G"),
    35: ("h", "H"),
    36: ("j", "J"),
    37: ("k", "K"),
    38: ("l", "L"),
    39: (";", ":"),
    40: ("'", '"'),
    41: ("`", "~"),
    43: ("\\", "|"),
    44: ("z", "Z"),
    45: ("x", "X"),
    46: ("c", "C"),
    47: ("v", "V"),
    48: ("b", "B"),
    49: ("n", "N"),
    50: ("m", "M"),
    51: (",", "<"),
    52: (".", ">"),
    53: ("/", "?"),
    57: (" ", " "),
    71: ("7", "7"),
    72: ("8", "8"),
    73: ("9", "9"),
    75: ("4", "4"),
    76: ("5", "5"),
    77: ("6", "6"),
    79: ("1", "1"),
    80: ("2", "2"),
    81: ("3", "3"),
    82: ("0", "0"),
    83: (".", "."),
    98: ("/", "/"),
}


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


def decode_decimal_ascii_triplets(text):
    if not text.isdigit() or len(text) % 3 != 0:
        return None

    decoded = []
    for index in range(0, len(text), 3):
        value = int(text[index:index + 3])
        if not 32 <= value <= 126:
            return None
        decoded.append(chr(value))

    return "".join(decoded)


def normalize_keyboard_scan(text):
    normalized = text.strip()
    if not normalized:
        return normalized

    triplet_decoded = decode_decimal_ascii_triplets(normalized)
    if triplet_decoded:
        normalized = triplet_decoded

    translated = "".join(SHIFTED_DIGIT_TO_DIGIT.get(char, char) for char in normalized)
    if translated.isdigit():
        normalized = translated

    return normalized


def alt_digits_to_char(digits):
    if not digits:
        return None

    try:
        value = int("".join(digits))
    except ValueError:
        return None

    if not 32 <= value <= 126:
        return None

    return chr(value)


class SerialScanner:
    def __init__(self, device):
        self.device = device
        self.ser = serial.Serial(device, BAUD_RATE, timeout=0)

    def read_code(self):
        raw = self.ser.readline().rstrip()
        if not raw:
            return None
        decoded = raw.decode("utf-8", errors="replace").strip()
        return decoded or None

    def close(self):
        self.ser.close()


class HIDKeyboardScanner:
    def __init__(self, device):
        self.device = device
        self.fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
        self.shift_pressed = False
        self.alt_pressed = False
        self.alt_digits = []
        self.buffer = []

    def read_code(self):
        while True:
            ready, _, _ = select.select([self.fd], [], [], TIMEOUT)
            if not ready:
                return None

            payload = os.read(self.fd, INPUT_EVENT_STRUCT.size)
            if not payload:
                raise OSError(f"Input device disconnected: {self.device}")
            if len(payload) != INPUT_EVENT_STRUCT.size:
                continue

            _, _, event_type, code, value = INPUT_EVENT_STRUCT.unpack(payload)
            if event_type != EV_KEY:
                continue

            if code in SHIFT_KEYS:
                self.shift_pressed = value != 0
                continue

            if code in ALT_KEYS:
                if value == 1:
                    self.alt_pressed = True
                    self.alt_digits.clear()
                elif value == 0:
                    self.alt_pressed = False
                    decoded = alt_digits_to_char(self.alt_digits)
                    self.alt_digits.clear()
                    if decoded:
                        self.buffer.append(decoded)
                continue

            if value != 1:
                continue

            if self.alt_pressed:
                digit = ALT_DIGIT_KEYMAP.get(code)
                if digit is not None:
                    self.alt_digits.append(digit)
                    continue

            if code in ENTER_KEYS:
                decoded = normalize_keyboard_scan("".join(self.buffer))
                self.buffer.clear()
                if decoded:
                    return decoded
                continue

            chars = HID_KEYMAP.get(code)
            if not chars:
                continue

            self.buffer.append(chars[1] if self.shift_pressed else chars[0])

    def close(self):
        os.close(self.fd)


def is_hid_device(device):
    return "/dev/input/" in device


def detect_hid_keyboard_devices():
    devices = sorted(glob("/dev/input/by-id/usb-*-event-kbd"))
    scanner_like = [
        device for device in devices
        if any(token in os_path.basename(device).lower() for token in ("barcode", "scanner"))
    ]
    return scanner_like or devices


def discover_scanner_devices():
    preferred = [USB_DEVICE_1, USB_DEVICE_2]
    candidates = []
    candidates.extend(preferred)
    candidates.extend(sorted(glob("/dev/ttyACM*")))
    candidates.extend(sorted(glob("/dev/ttyUSB*")))
    candidates.extend(detect_hid_keyboard_devices())

    resolved = []
    seen = set()
    for device in candidates:
        if not device or device in seen or not os_path.exists(device):
            continue
        seen.add(device)
        resolved.append(device)

    return resolved


def open_scanner(device):
    if is_hid_device(device):
        return HIDKeyboardScanner(device), "hid-keyboard"
    return SerialScanner(device), f"serial @ {BAUD_RATE} baud"


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
        scanner, scanner_type = open_scanner(device)
        print(f"[{prefix}] Opened {device} ({scanner_type})")
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
                decoded = scanner.read_code()
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
    scanner.close()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    devices = discover_scanner_devices()
    scanner_plan = list(zip((FILE_PREFIX_1, FILE_PREFIX_2), devices[:2]))

    if not scanner_plan:
        print("No scanner devices found. Checked serial ports and /dev/input/by-id/usb-*-event-kbd.")
        raise SystemExit(1)

    print(f"Starting QR scanner app with {len(scanner_plan)} device(s)")
    for prefix, device in scanner_plan:
        print(f"[{prefix}] Using {device}")

    processes = [
        Process(target=scanner_loop, args=(device, prefix))
        for prefix, device in scanner_plan
    ]

    for process in processes:
        process.start()

    for process in processes:
        process.join()

    print("QR scanner app stopped.")

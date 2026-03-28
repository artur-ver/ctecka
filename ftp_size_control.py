#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import time
from datetime import datetime
from ftplib import FTP, error_perm
from send import upload_file_to_ftp_server
from config import FTP_HOST, FTP_USER, FTP_PASS, REMOTE_ROOT, LOG_DIR_ROOT


def get_local_log_files():
    # get today's logs
    today = datetime.now().strftime('%Y-%m-%d')
    dir_path = os.path.join(LOG_DIR_ROOT, today)
    if not os.path.isdir(dir_path):
        return []
    return [os.path.join(dir_path, f) for f in os.listdir(dir_path)
            if f.endswith('.log')]


def connect_ftp() -> FTP:
    # connect ftp, binary mode
    ftp = FTP(FTP_HOST)
    ftp.login(FTP_USER, FTP_PASS)
    ftp.cwd(REMOTE_ROOT)
    ftp.voidcmd('TYPE I')  # binary mode
    return ftp


def get_remote_file_size(ftp: FTP, filename: str) -> int:
    # get remote file size
    try:
        size = ftp.size(filename)
        return size or 0
    except error_perm as e:
        print(f"[Error] can't get size of remote '{filename}': {e}")
        return 0
    except Exception as e:
        print(f"[Error] unexpected error getting size of remote '{filename}': {e}")
        return 0


def get_remote_file_exists(ftp: FTP, filename: str) -> bool:
    # check if remote file exists
    try:
        ftp.size(filename)
        return True
    except error_perm as e:
        if str(e).startswith('550'):
            return False
        print(f"[Error] can't check existence of remote '{filename}': {e}")
        return False
    except Exception as e:
        print(f"[Error] unexpected error checking existence of remote '{filename}': {e}")
        return False


def sync_file(local_path: str):
    # sync one file
    filename = os.path.basename(local_path)
    local_size = os.path.getsize(local_path)

    try:
        ftp = connect_ftp()
    except Exception as e:
        print(f"[Error] FTP connection error: {e}")
        print(f"[Error] Cannot compare or send '{filename}' due to FTP connection error.")
        return

    try:
        remote_size = get_remote_file_size(ftp, filename)
    except Exception as e:
        print(f"[Error] Cannot compare '{filename}' on server: {e}")
        ftp.quit()
        return
    ftp.quit()
    if local_size <= remote_size:
        print(f"[Info] '{filename}': local size ({local_size}) <= remote size ({remote_size}), skip")
        return

    print(f"[Sync] '{filename}': local {local_size} > remote {remote_size}, uploading...")
    while True:
        try:
            upload_file_to_ftp_server(local_path, FTP_HOST, FTP_USER, FTP_PASS)
        except Exception as e:
            print(f"[Error] upload failed for '{filename}': {e}")
            print(f"[Error] Cannot send '{filename}' to server.")
            time.sleep(5)
            continue

        try:
            ftp = connect_ftp()
            remote_size = get_remote_file_size(ftp, filename)
            ftp.quit()
        except Exception as e:
            print(f"[Error] error checking remote size after upload: {e}")
            print(f"[Error] Cannot compare '{filename}' after upload.")
            remote_size = 0

        print(f"[Check] '{filename}': after upload remote size is {remote_size}")
        if remote_size >= local_size:
            print(f"[Done] '{filename}' synchronized ({local_size} bytes)")
            break
        else:
            print(f"[Retry] sizes differ: local {local_size} vs remote {remote_size}, retry")
            time.sleep(5)


def main(nsent_txt=None):
    print(f"Start sync at {datetime.now():%Y-%m-%d %H:%M:%S}")
    if nsent_txt is None:
        nsent_txt = os.path.join(os.path.dirname(__file__), "nsent_logs.txt")
    if os.path.exists(nsent_txt):
        with open(nsent_txt, "r") as f:
            only_files = set(line.strip() for line in f if line.strip())
        files = get_local_log_files()
        files_to_check = [f for f in files if os.path.basename(f) in only_files]
        total = len(files_to_check)
        changed = 0
        if not files_to_check:
            print("[Info] no log files to check, exiting...")
        for f in files_to_check:
            filename = os.path.basename(f)
            local_size = os.path.getsize(f)
            try:
                ftp = connect_ftp()
                file_exists = get_remote_file_exists(ftp, filename)
                if not file_exists:
                    print(f"[Skip] '{filename}': not found on server, skipping")
                    ftp.quit()
                    continue
                remote_size = get_remote_file_size(ftp, filename)
                ftp.quit()
            except Exception as e:
                print(f"[Error] FTP connection error: {e}")
                continue
            if local_size > remote_size:
                changed += 1
            sync_file(f)
        print(f"[Info] checked {total} files, changed {changed} files")
        print("[Info] done.")
        return
    else:
        print("[Info] nsent_logs.txt not found, nothing to check.")
        return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="ftp_size_control.py")
    parser.add_argument("--nsent-file", dest="nsent_file", default=None)
    args = parser.parse_args()
    main(args.nsent_file)


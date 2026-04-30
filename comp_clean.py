#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import gzip
import shutil
from os import path as os_path
from pathlib import Path
from config import LOG_DIR_ROOT, COMPRESS_OLD_LOGS_DAYS, MAX_USED_PERCENT


def compress_and_cleanup(log_dir_root, compress_days, max_used_pct, log_print=None, log_type_error=None):
    """
    Compress old .log files and reclaim disk space.

    - Compresses .log files older than compress_days days to .gz
    - If disk usage exceeds max_used_pct, deletes oldest .gz files until
      usage drops below the threshold.
    """
    try:
        cutoff_time = time.time() - (compress_days * 86400)

        # Compress old .log files
        for root, _, files in os.walk(log_dir_root):
            for file in files:
                if file.endswith(".log"):
                    file_path = os_path.join(root, file)
                    if os_path.getmtime(file_path) < cutoff_time:
                        try:
                            with open(file_path, 'rb') as f_in:
                                with gzip.open(f"{file_path}.gz", 'wb') as f_out:
                                    shutil.copyfileobj(f_in, f_out)
                            os.remove(file_path)
                            print(f"Compressed '{file}' in '{root}'")
                            time.sleep(5)  # brief pause between compressions
                        except Exception as e:
                            print(f"Error compressing {file_path}: {e}")

        # Check disk usage
        stat = shutil.disk_usage(log_dir_root)
        used_percent = 100 * (stat.total - stat.free) / stat.total
        if used_percent < max_used_pct:
            return

        # Collect all .gz files, oldest first
        gz_files = []
        for root, _, files in os.walk(log_dir_root):
            for file in files:
                if file.endswith(".gz"):
                    fp = os_path.join(root, file)
                    gz_files.append((fp, os_path.getmtime(fp)))
        gz_files.sort(key=lambda x: x[1])

        # Delete oldest .gz files until disk usage is acceptable
        while gz_files and used_percent >= max_used_pct:
            oldest_file = gz_files.pop(0)[0]
            os.remove(oldest_file)
            stat = shutil.disk_usage(log_dir_root)
            used_percent = 100 * (stat.total - stat.free) / stat.total

    except Exception as e:
        if log_print:
            log_print(f"Cleanup error: {e}", log_type_error)
        else:
            print(f"Cleanup error: {e}")


def main():
    while True:
        try:
            compress_and_cleanup(LOG_DIR_ROOT, COMPRESS_OLD_LOGS_DAYS, MAX_USED_PERCENT)
        except Exception as e:
            print(f"Main loop error: {e}")
        time.sleep(240)  # run every 4 minutes


if __name__ == "__main__":
    print("comp_clean.py started")
    main()

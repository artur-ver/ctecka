import os
import time
import gzip
import shutil
from datetime import datetime
from os import path as os_path
from pathlib import Path
from config import LOG_DIR_ROOT, COMPRESS_OLD_LOGS_DAYS, MAX_USED_PERCENT

def compress_and_cleanup(LOG_DIR_ROOT, COMPRESS_OLD_LOGS_DAYS, MAX_USED_PERCENT, log_print=None, LOG_TYPE_ERROR=None):
    """
    Compress old .log files and clean up disk space in the log directory.
    - Compresses .log files older than COMPRESS_OLD_LOGS_DAYS days to .gz
    - If disk usage is above MAX_USED_PERCENT, deletes oldest .gz files until usage is below threshold
    """
    try:
        # Calculate cutoff time for old logs
        cutoff_time = time.time() - (COMPRESS_OLD_LOGS_DAYS * 86400)
        # Compress old .log files
        for root, _, files in os.walk(LOG_DIR_ROOT):
            for file in files:
                if file.endswith(".log"):

                    file_path = os_path.join(root, file)
                    if os_path.getmtime(file_path) < cutoff_time:
                        try:
                            with open(file_path, 'rb') as f_in:
                                with gzip.open(f"{file_path}.gz", 'wb') as f_out:
                                    shutil.copyfileobj(f_in, f_out)
                            os.remove(file_path)
                            print(f"log '{file}' was compressed in folder '{root}'")

                            time.sleep(5)  # Add 5s delay between compressions

                        except Exception as e:
                            print(f"Error compressing {file_path}: {e}")
        # Check disk usage percent
        stat = shutil.disk_usage(LOG_DIR_ROOT)
        used_percent = 100 * (stat.total - stat.free) / stat.total
        if used_percent < MAX_USED_PERCENT:
            return
        # Collect all .gz files for possible deletion
        gz_files = []
        for root, _, files in os.walk(LOG_DIR_ROOT):
            for file in files:
                if file.endswith(".gz"):
                    file_path = os_path.join(root, file)
                    gz_files.append((file_path, os_path.getmtime(file_path)))
        # Sort .gz files by modification time (oldest first)
        gz_files.sort(key=lambda x: x[1])
        # Delete oldest .gz files until disk usage is below threshold
        while gz_files and used_percent >= MAX_USED_PERCENT:
            oldest_file = gz_files.pop(0)[0]
            os.remove(oldest_file)
            stat = shutil.disk_usage(LOG_DIR_ROOT)
            used_percent = 100 * (stat.total - stat.free) / stat.total
    except Exception as e:
        # Log or print cleanup errors
        if log_print:
            log_print(f"Cleanup error: {e}", LOG_TYPE_ERROR)
        else:
            print(f"Cleanup error: {e}")

def main():
    while True:
        try:
            compress_and_cleanup(LOG_DIR_ROOT, COMPRESS_OLD_LOGS_DAYS, MAX_USED_PERCENT)
        except Exception as e:
            print(f"Main loop error: {e}")
        time.sleep(240)  # Check every 4 minutes

if __name__ == "__main__":
    print("i am comp_clean.py")
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os.path
import sys
import ftplib
import time
from config import FTP_HOST, FTP_USER, FTP_PASS, REMOTE_ROOT

# upload file to ftp
def upload_file_to_ftp_server(file_path, ftp_server_address=FTP_HOST, ftp_username=FTP_USER, ftp_password=FTP_PASS):
    with ftplib.FTP(ftp_server_address) as ftp:
        ftp.login(user=ftp_username, passwd=ftp_password)
        with open(file_path, 'rb') as file:
            ftp.storbinary(f'STOR {REMOTE_ROOT}/{os.path.split(file_path)[1]}', file)

if __name__ == '__main__':
    # check args
    if len(sys.argv) < 2:
        print("Please provide a file location as an argument.")
        sys.exit(1)
    file_path = sys.argv[1]

    # check file
    if not os.path.exists(file_path):
        print(f"The file at {file_path} does not exist.")
        sys.exit(1)
    # send file
    upload_file_to_ftp_server(file_path)
    print(f"send.py [FILE UPLOADED] {file_path}")
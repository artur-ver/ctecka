#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import main_loop
from config import CISLO_DRAHY2, SERIAL_DEVICE2


if __name__ == "__main__":
    while True:
        try:
            main_loop(serial_device=SERIAL_DEVICE2, track_code=CISLO_DRAHY2)
        except Exception as e:
            print(f"Fatal error: {e}")

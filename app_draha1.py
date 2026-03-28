#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import main_loop
from config import CISLO_DRAHY, SERIAL_DEVICE


if __name__ == "__main__":
    while True:
        try:
            main_loop(serial_device=SERIAL_DEVICE, track_code=CISLO_DRAHY)
        except Exception as e:
            print(f"Fatal error: {e}")

import evdev
from evdev import InputDevice, ecodes
import threading
import time
import os

# Фиксированные пути по ПОРТАМ
scanners_config = [
    {
        'path': '/dev/input/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.1:1.0-event-kbd',
        'file': '/home/kyje01/1.txt'
    },
    {
        'path': '/dev/input/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.2:1.0-event-kbd',
        'file': '/home/kyje01/2.txt'
    }
]

def read_scanner(config):
    while True:
        try:
            if os.path.exists(config['path']):
                device = InputDevice(config['path'])
                device.grab()  # Перехват ввода (чтобы не писало в консоль)
                barcode = ""
                
                for event in device.read_loop():
                    if event.type == ecodes.EV_KEY and event.value == 1:
                        key = evdev.categorize(event).keycode
                        if key == 'KEY_ENTER':
                            if barcode:
                                with open(config['file'], "a") as f:
                                    f.write(f"{barcode}\n")
                                barcode = ""
                        elif 'KEY_' in key:
                            char = key.replace('KEY_', '')
                            if len(char) == 1: 
                                barcode += char
                            elif char.isdigit(): # Обработка цифр (KEY_1, KEY_2 и т.д.)
                                barcode += char[-1]
            else:
                time.sleep(2)
        except Exception:
            time.sleep(5)

for cfg in scanners_config:
    threading.Thread(target=read_scanner, args=(cfg,), daemon=True).start()

while True:
    time.sleep(1)
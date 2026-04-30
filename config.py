import os

# Centralized configuration for QR scanner project

# File prefixes for each QR scanner device
FILE_PREFIX_1 = 'QR1'
FILE_PREFIX_2 = 'QR2'

# FTP credentials
FTP_HOST = '192.168.0.179'
FTP_USER = 'user'
FTP_PASS = '12345'

REMOTE_ROOT = '/'

# Local log directory (relative to script location)
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
LOG_DIR_ROOT = os.path.join(SCRIPT_DIR, 'logs')

# Preferred scanner device paths.
# app.py first tries these explicit paths, then falls back to auto-detection:
#   - serial scanners on /dev/ttyACM* and /dev/ttyUSB*
#   - HID keyboard scanners on /dev/input/by-id/usb-*-event-kbd
USB_DEVICE_1 = "/dev/ttyACM0"
USB_DEVICE_2 = "/dev/ttyACM1"

# USB serial baud rate (most QR scanners use 9600)
BAUD_RATE = 9600

TIMEOUT = 0.01  # seconds (serial read loop delay)

LOG_TIME = 5  # minutes per log file

TIME_FORMAT = "%Y%m%d-%H%M%S"

# Log entry types
LOG_TYPE_LOG = "Log"
LOG_TYPE_INFO = "Info"
LOG_TYPE_ERROR = "Error"

# Compression and cleanup settings
COMPRESS_OLD_LOGS_DAYS = 30
MAX_USED_PERCENT = 95  # Delete .gz files if disk is above this %

# Centralized sudo handling for reboot requests.
# Use non-interactive sudo and configure passwordless access for reboot once
# on the Raspberry Pi instead of storing a plaintext password in the repo.
SUDO_REBOOT_COMMANDS = (
	("/usr/sbin/reboot",),
	("/sbin/reboot",),
)
SUDOERS_REBOOT_HINT = (
	"Create /etc/sudoers.d/ctecka-reboot with NOPASSWD access for "
	"/usr/sbin/reboot and /sbin/reboot."
)


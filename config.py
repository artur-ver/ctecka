import os

# Centralized configuration for all scripts

CISLO_DRAHY = 'A1'
SERIAL_DEVICE = "/dev/ttyUSB0"


CISLO_DRAHY2 = 'A2'
SERIAL_DEVICE2 = "/dev/ttyUSB1"


FTP_HOST = '0.0.0.0'
FTP_USER = 'user'
FTP_PASS = '1234'


REMOTE_ROOT = '/'





# Local log directory (relative to script location)

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
LOG_DIR_ROOT = os.path.join(SCRIPT_DIR, 'logs')


# Serial port and logging

TIMEOUT = 0.01  # seconds

LOG_TIME = 5  # minutes



TIME_FORMAT = "%Y%m%d-%H%M%S"



# Log types
LOG_TYPE_LOG = "Log"
LOG_TYPE_INFO = "Info"
LOG_TYPE_ERROR = "Error"




# Compression and cleanup settings

COMPRESS_OLD_LOGS_DAYS = 30
MAX_USED_PERCENT = 95 # Delete if disk is 95% full


# internet.py
EMAIL_TO = ["arturverbovsuk@gmail.com", "l.glaser@schubert.cz", "m.trikal@schubert.cz"]

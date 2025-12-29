import configparser
import os
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError

APP_KEY = "jd_shell_cli"

try:
    VERSION = version("jd-shell-cli") 
except PackageNotFoundError:
    VERSION = "0.0.0"

config_path = Path.home() / ".config" / "jdsh" / "jdsh.conf"

parser = configparser.ConfigParser()
parser.read(config_path)

HOST = parser.get("settings", "host", fallback="127.0.0.1")
PORT = parser.getint("settings", "port", fallback=3128)
REFRESH_RATE = parser.getfloat("settings", "refresh_rate", fallback=1.0)

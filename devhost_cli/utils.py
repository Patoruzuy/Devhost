"""Console output utilities and colors"""

import os
import sys


class Colors:
    """ANSI colors for terminal output"""

    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    GRAY = "\033[90m"

    @classmethod
    def disable(cls):
        """Disable colors for non-TTY or Windows without ANSI support"""
        cls.RESET = cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.GRAY = ""


# Initialize colors based on environment
if os.environ.get("NO_COLOR"):
    Colors.disable()
elif not sys.stdout.isatty():
    Colors.disable()
elif sys.platform == "win32":
    try:
        os.system("")  # Enable ANSI support on Windows
    except Exception:
        pass


ICON_SUCCESS = "[ok]"
ICON_ERROR = "[x]"
ICON_WARN = "[!]"
ICON_INFO = ">"
ICON_UP = "+"
ICON_DOWN = "-"


def msg_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}{ICON_SUCCESS}{Colors.RESET} {text}")


def msg_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}{ICON_ERROR}{Colors.RESET} {text}", file=sys.stderr)


def msg_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}{ICON_WARN}{Colors.RESET} {text}")


def msg_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}{ICON_INFO}{Colors.RESET} {text}")


def msg_step(current: int, total: int, text: str):
    """Print step message"""
    print(f"{Colors.GRAY}[{current}/{total}]{Colors.RESET} {text}")

"""Log management for devhost router."""

import os
import sys
import time
from pathlib import Path

from .platform import IS_WINDOWS
from .utils import msg_error, msg_info, msg_success, msg_warning


def get_log_path() -> Path:
    """Get the router log file path.

    Priority:
    1. DEVHOST_LOG_FILE environment variable
    2. ~/.devhost/router.log
    3. Windows temp directory fallback
    """
    # Check environment variable first
    env_path = os.getenv("DEVHOST_LOG_FILE")
    if env_path:
        return Path(env_path)

    # Default location
    devhost_dir = Path.home() / ".devhost"
    if devhost_dir.exists() or not IS_WINDOWS:
        return devhost_dir / "router.log"

    # Windows fallback to temp
    temp = os.environ.get("TEMP", os.environ.get("TMP", ""))
    if temp:
        return Path(temp) / "devhost-router.log"

    return devhost_dir / "router.log"


def cmd_logs(follow: bool = False, lines: int = 50, clear: bool = False) -> bool:
    """Tail router logs.

    Args:
        follow: If True, continuously follow log output (like tail -f)
        lines: Number of lines to show initially
        clear: If True, clear the log file instead of reading it

    Returns:
        True if successful, False otherwise
    """
    log_path = get_log_path()

    if clear:
        if log_path.exists():
            try:
                log_path.write_text("")
                msg_success(f"Cleared log file: {log_path}")
                return True
            except PermissionError:
                msg_error(f"Permission denied: {log_path}")
                return False
            except Exception as e:
                msg_error(f"Failed to clear log: {e}")
                return False
        else:
            msg_info(f"Log file does not exist: {log_path}")
            return True

    if not log_path.exists():
        msg_warning(f"Log file not found: {log_path}")
        msg_info("Router may not be running or logging is disabled.")
        msg_info("To enable logging, start the router with DEVHOST_LOG_FILE set:")
        msg_info(f"  export DEVHOST_LOG_FILE={log_path}")
        return True

    try:
        # Read initial lines
        content = log_path.read_text(encoding="utf-8", errors="replace")
        all_lines = content.splitlines()

        if lines > 0 and len(all_lines) > lines:
            display_lines = all_lines[-lines:]
            print(f"... (showing last {lines} of {len(all_lines)} lines)")
        else:
            display_lines = all_lines

        for line in display_lines:
            print(line)

        if not follow:
            return True

        # Follow mode - watch for changes
        msg_info(f"Following {log_path} (Ctrl+C to stop)...")
        last_size = log_path.stat().st_size

        try:
            while True:
                time.sleep(0.5)

                if not log_path.exists():
                    msg_warning("Log file was deleted. Waiting for recreation...")
                    while not log_path.exists():
                        time.sleep(1)
                    last_size = 0
                    msg_info("Log file recreated. Resuming...")

                current_size = log_path.stat().st_size

                if current_size > last_size:
                    # New content added
                    with log_path.open("r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_size)
                        new_content = f.read()
                        sys.stdout.write(new_content)
                        sys.stdout.flush()
                    last_size = current_size
                elif current_size < last_size:
                    # File was truncated (cleared)
                    msg_info("(Log file was cleared)")
                    last_size = current_size

        except KeyboardInterrupt:
            print()  # Clean line after ^C
            return True

    except PermissionError:
        msg_error(f"Permission denied reading: {log_path}")
        return False
    except Exception as e:
        msg_error(f"Failed to read log: {e}")
        return False

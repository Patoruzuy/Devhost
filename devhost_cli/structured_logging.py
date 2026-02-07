"""
Structured logging support for production observability (Phase 4 L-16).

Provides JSON-formatted logging when enabled via DEVHOST_LOG_FORMAT=json.
Includes request ID tracking and structured fields for easier log ingestion.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Outputs logs in JSON format with structured fields:
    - timestamp: ISO 8601 timestamp
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - logger: Logger name
    - message: Log message
    - request_id: Optional request ID for correlation
    - extra: Any additional fields from LogRecord
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as JSON.

        Args:
            record: LogRecord to format

        Returns:
            JSON string representation of the log entry
        """
        # Create ISO 8601 timestamp with milliseconds

        dt = datetime.fromtimestamp(record.created)
        timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(record.msecs):03d}Z"

        log_entry: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request ID if present
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_entry["request_id"] = request_id

        # Add pathname and line number for debugging
        if record.pathname:
            log_entry["file"] = f"{record.filename}:{record.lineno}"

        # Add function name
        if record.funcName and record.funcName != "<module>":
            log_entry["function"] = record.funcName

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add any extra fields that were passed to the logger
        # Exclude private fields and known fields
        excluded_fields = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
            "request_id",
        }

        for key, value in record.__dict__.items():
            if key not in excluded_fields and not key.startswith("_"):
                log_entry[key] = value

        return json.dumps(log_entry)


def configure_structured_logging(level: str = "INFO", log_file: str | None = None, force: bool = True) -> None:
    """
    Configure structured JSON logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        force: Force reconfiguration of root logger
    """
    handlers = []

    # Console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    handlers.append(console_handler)

    # File handler if specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(JSONFormatter())
            handlers.append(file_handler)
        except Exception as e:
            # Fallback to console only if file fails
            print(f"Warning: Could not open log file {log_file}: {e}", file=sys.stderr)

    logging.basicConfig(
        level=level.upper(),
        handlers=handlers,
        force=force,
    )


def is_json_logging_enabled() -> bool:
    """
    Check if JSON logging is enabled via environment variable.

    Returns:
        True if DEVHOST_LOG_FORMAT=json, False otherwise
    """
    log_format = os.getenv("DEVHOST_LOG_FORMAT", "text").lower()
    return log_format == "json"


def setup_logging(level: str | None = None, log_file: str | None = None, force: bool = True) -> None:
    """
    Setup logging based on environment variables.

    Environment variables:
    - DEVHOST_LOG_FORMAT: "json" or "text" (default: text)
    - DEVHOST_LOG_LEVEL: Log level (default: INFO)
    - DEVHOST_LOG_FILE: Optional log file path

    Args:
        level: Override log level (uses DEVHOST_LOG_LEVEL if None)
        log_file: Override log file (uses DEVHOST_LOG_FILE if None)
        force: Force reconfiguration of root logger
    """
    # Get configuration from environment
    if level is None:
        level = os.getenv("DEVHOST_LOG_LEVEL", "INFO")

    if log_file is None:
        log_file = os.getenv("DEVHOST_LOG_FILE")

    # Configure based on format
    if is_json_logging_enabled():
        configure_structured_logging(level=level, log_file=log_file, force=force)
    else:
        # Standard text logging
        handlers = [logging.StreamHandler(sys.stdout)]
        if log_file:
            try:
                handlers.append(logging.FileHandler(log_file))
            except Exception:
                pass

        logging.basicConfig(
            level=level.upper(),
            format="%(asctime)s %(levelname)s %(name)s - %(message)s",
            handlers=handlers,
            force=force,
        )


class RequestLogger:
    """
    Helper class for adding request ID context to logs.

    Usage:
        logger = logging.getLogger(__name__)
        request_logger = RequestLogger(logger, request_id="abc123")
        request_logger.info("Processing request")  # Includes request_id
    """

    def __init__(self, logger: logging.Logger, request_id: str):
        self.logger = logger
        self.request_id = request_id

    def _log(self, level: int, msg: str, *args, **kwargs):
        """Add request_id to log record."""
        extra = kwargs.get("extra", {})
        extra["request_id"] = self.request_id
        kwargs["extra"] = extra
        self.logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message with request ID."""
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message with request ID."""
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message with request ID."""
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message with request ID."""
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message with request ID."""
        self._log(logging.CRITICAL, msg, *args, **kwargs)

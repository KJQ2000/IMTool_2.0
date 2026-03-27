"""
logging_config.py
-----------------
Centralized, production-oriented logging configuration.

Key features:
  - Date-folder log storage for operational readability
  - Dedicated error log stream for incident triage
  - Context-aware fields (trace_id, user_email) on every record
  - Idempotent setup safe for Streamlit reruns
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from utils.log_context import get_log_context


_CONFIGURED = False


class _ContextFilter(logging.Filter):
    """Inject request/user context into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = get_log_context()
        record.trace_id = context.get("trace_id", "-")
        record.user_email = context.get("user_email", "-")
        return True


class _DailyDirectoryFileHandler(logging.FileHandler):
    """Write logs into ``logs/YYYY-MM-DD/YYYY-MM-DD_HH-MM-SS[_name].log``."""

    def __init__(
        self,
        log_root: Path,
        *,
        filename_suffix: str = "",
        retention_days: int = 30,
    ) -> None:
        self._log_root = log_root
        self._filename_suffix = filename_suffix
        self._retention_days = retention_days
        current_dt = datetime.now().astimezone()
        log_path = self._build_log_path(current_dt)
        self._active_date = current_dt.date()
        super().__init__(log_path, encoding="utf-8", delay=False)
        self._cleanup_old_log_dirs(current_dt)

    def _build_log_path(self, current_dt: datetime) -> Path:
        date_str = current_dt.strftime("%Y-%m-%d")
        timestamp_str = current_dt.strftime("%Y-%m-%d_%H-%M-%S")
        day_dir = self._log_root / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir / f"{timestamp_str}{self._filename_suffix}.log"

    def _cleanup_old_log_dirs(self, current_dt: datetime) -> None:
        if self._retention_days <= 0 or not self._log_root.exists():
            return

        cutoff_date = current_dt.date() - timedelta(days=self._retention_days)
        for entry in self._log_root.iterdir():
            if not entry.is_dir():
                continue
            try:
                entry_date = datetime.strptime(entry.name, "%Y-%m-%d").date()
            except ValueError:
                continue
            if entry_date < cutoff_date:
                shutil.rmtree(entry, ignore_errors=True)

    def _rollover_if_needed(self) -> None:
        current_dt = datetime.now().astimezone()
        current_date = current_dt.date()
        if current_date == self._active_date:
            return

        if self.stream:
            self.stream.close()
            self.stream = None

        next_path = self._build_log_path(current_dt)
        self.baseFilename = os.fspath(next_path.resolve())
        self._active_date = current_date
        self.stream = self._open()
        self._cleanup_old_log_dirs(current_dt)

    def emit(self, record: logging.LogRecord) -> None:
        self._rollover_if_needed()
        super().emit(record)


def configure_logging(log_level: str | None = None) -> None:
    """Set up root logging with date-folder files and console output.

    Safe to call multiple times — subsequent calls are no-ops.

    Parameters
    ----------
    log_level:
        Override log level (e.g. "DEBUG", "INFO"). Defaults to the
        ``LOG_LEVEL`` environment variable, falling back to "INFO".
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    level_str = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_str, logging.INFO)

    # Ensure logs directory exists
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    retention_days = int(os.getenv("LOG_RETENTION_DAYS", "30"))

    # ISO format with strong execution context
    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | "
        "trace=%(trace_id)s user=%(user_email)s | %(message)s"
    )
    datefmt = "%Y-%m-%dT%H:%M:%S%z"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
    context_filter = _ContextFilter()

    # Application log for the active run
    app_file_handler = _DailyDirectoryFileHandler(
        log_dir,
        retention_days=retention_days,
    )
    app_file_handler.setLevel(level)
    app_file_handler.setFormatter(formatter)
    app_file_handler.addFilter(context_filter)

    # Error-only log for the active run
    error_file_handler = _DailyDirectoryFileHandler(
        log_dir,
        filename_suffix="_error",
        retention_days=retention_days,
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    error_file_handler.addFilter(context_filter)

    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(app_file_handler)
    root_logger.addHandler(error_file_handler)
    root_logger.addHandler(stream_handler)
    root_logger.info(
        "Logging configured: level=%s retention_days=%d dir=%s app_file=%s error_file=%s",
        logging.getLevelName(level),
        retention_days,
        log_dir,
        app_file_handler.baseFilename,
        error_file_handler.baseFilename,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring logging is configured first.

    Parameters
    ----------
    name:
        Logger name — typically ``__name__`` from the calling module.
    """
    configure_logging()
    return logging.getLogger(name)

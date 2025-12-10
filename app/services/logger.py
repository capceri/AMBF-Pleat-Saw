"""
Logging service for Pleat Saw controller.
Configures Python logging with file rotation and console output.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[str] = None,
    max_bytes: int = 10485760,  # 10 MB
    backup_count: int = 5,
    console_output: bool = True
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files (default: /var/log/pleat_saw)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
        console_output: Enable console output

    Returns:
        Root logger instance
    """
    # Get root logger
    logger = logging.getLogger()

    # Clear any existing handlers
    logger.handlers.clear()

    # Set log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler (with rotation)
    if log_dir:
        log_dir_path = Path(log_dir)

        # Create log directory if it doesn't exist
        try:
            log_dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create log directory {log_dir}: {e}")
            return logger

        log_file = log_dir_path / "pleat_saw.log"

        try:
            file_handler = logging.handlers.RotatingFileHandler(
                filename=str(log_file),
                maxBytes=max_bytes,
                backupCount=backup_count,
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            logger.info(f"Logging to file: {log_file}")

        except Exception as e:
            logger.error(f"Failed to create file handler: {e}")

    logger.info(f"Logging initialized: level={level}")

    return logger


class EventLogger:
    """
    Event logger for tracking machine events and statistics.
    Logs process cycles, alarms, I/O changes, etc.
    """

    def __init__(self, log_dir: Optional[str] = None):
        """
        Initialize event logger.

        Args:
            log_dir: Directory for event log files
        """
        self.logger = logging.getLogger("pleat_saw.events")

        if log_dir:
            log_dir_path = Path(log_dir)
            log_dir_path.mkdir(parents=True, exist_ok=True)

            event_log_file = log_dir_path / "events.log"

            try:
                handler = logging.handlers.RotatingFileHandler(
                    filename=str(event_log_file),
                    maxBytes=10485760,  # 10 MB
                    backupCount=10,
                )

                formatter = logging.Formatter(
                    fmt='%(asctime)s,%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )

                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)

            except Exception as e:
                logging.error(f"Failed to create event log handler: {e}")

    def log_event(self, event_type: str, **kwargs):
        """
        Log a machine event.

        Args:
            event_type: Type of event (e.g., "CYCLE_START", "ALARM", "INPUT_CHANGE")
            **kwargs: Additional event data as key=value pairs
        """
        # Format as CSV-like string
        data = [event_type]
        for key, value in kwargs.items():
            data.append(f"{key}={value}")

        message = ",".join(data)
        self.logger.info(message)

    def log_cycle_start(self):
        """Log cycle start event."""
        self.log_event("CYCLE_START")

    def log_cycle_complete(self, duration_s: float):
        """Log cycle complete event."""
        self.log_event("CYCLE_COMPLETE", duration_s=f"{duration_s:.3f}")

    def log_alarm(self, alarm_code: str, state: str):
        """Log alarm event."""
        self.log_event("ALARM", code=alarm_code, state=state)

    def log_input_change(self, input_name: str, state: bool):
        """Log input change event."""
        self.log_event("INPUT_CHANGE", input=input_name, state=int(state))

    def log_output_change(self, output_name: str, state: bool):
        """Log output change event."""
        self.log_event("OUTPUT_CHANGE", output=output_name, state=int(state))

    def log_estop(self):
        """Log emergency stop event."""
        self.log_event("ESTOP")

    def log_reset(self):
        """Log alarm reset event."""
        self.log_event("RESET")


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger instance.

    Args:
        name: Logger name (typically module name)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)

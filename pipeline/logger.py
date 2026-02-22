import logging
import sys
from datetime import datetime
from typing import Any


def setup_logger(name: str = "daily_papers", log_file: str | None = None) -> logging.Logger:
    """Configure structured logging for the pipeline."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


class ErrorTracker:
    """Track errors during pipeline execution."""

    errors: list[dict[str, Any]]

    def __init__(self) -> None:
        self.errors = []

    def add_error(self, stage: str, error: Exception) -> None:
        """Record an error."""
        self.errors.append(
            {
                "stage": stage,
                "error": str(error),
                "type": type(error).__name__,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def has_errors(self) -> bool:
        """Check if any errors were recorded."""
        return len(self.errors) > 0

    def get_summary(self) -> str:
        """Get a formatted error summary."""
        if not self.errors:
            return "No errors occurred."

        lines = [f"\n{'=' * 60}", "Error Summary:", f"{'=' * 60}"]
        for i, err in enumerate(self.errors, 1):
            lines.append(f"\n{i}. [{err['stage']}] {err['type']}: {err['error']}")
        lines.append(f"{'=' * 60}\n")

        return "\n".join(lines)

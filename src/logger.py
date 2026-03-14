"""
logger.py
---------
Structured logging for the DDR pipeline.
Provides a central logger with timing and stage-level tracking.
"""

import logging
import time
import functools
from datetime import datetime


def get_logger(name: str = "ddr_pipeline") -> logging.Logger:
    """Get or create a named logger with consistent formatting."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class PipelineTimer:
    """Context manager for timing pipeline stages."""

    def __init__(self, stage_name: str, logger: logging.Logger = None):
        self.stage_name = stage_name
        self.logger = logger or get_logger()
        self.start_time = None
        self.elapsed = 0.0

    def __enter__(self):
        self.start_time = time.time()
        self.logger.info("▶ %s — started", self.stage_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.time() - self.start_time
        if exc_type:
            self.logger.error(
                "✖ %s — FAILED after %.2fs: %s", self.stage_name, self.elapsed, exc_val
            )
        else:
            self.logger.info(
                "✔ %s — completed in %.2fs", self.stage_name, self.elapsed
            )
        return False


class PipelineMetrics:
    """Collects timing and count metrics across the full pipeline run."""

    def __init__(self):
        self.stages: list[dict] = []
        self.run_start = time.time()

    def record(self, stage: str, elapsed: float, **extra):
        self.stages.append({"stage": stage, "elapsed_s": round(elapsed, 2), **extra})

    def summary(self) -> dict:
        total = time.time() - self.run_start
        return {
            "total_elapsed_s": round(total, 2),
            "stages": self.stages,
        }

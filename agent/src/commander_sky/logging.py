"""Structured logging setup.

COPPA rule enforced here: log lines carry metrics and event names only —
NEVER conversation content, transcripts, or child audio references.
"""

import logging

import structlog


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structlog for JSON output with stdlib interop."""
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structured logger."""
    return structlog.get_logger(name)

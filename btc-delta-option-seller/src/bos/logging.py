from __future__ import annotations

import logging
import sys

import structlog

from bos.config import LoggingSettings


def configure_logging(settings: LoggingSettings) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.level.upper())
    renderer = (
        structlog.processors.JSONRenderer()
        if settings.json_output
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.level.upper())
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

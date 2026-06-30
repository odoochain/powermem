"""
Configure PowerMem logging with loguru sinks.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterable
from typing import Any

from loguru import logger as loguru_logger

from powermem.log_context import get_log_context

_DEFAULT_TEXT_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss,SSS} - {extra[logger_name]} - {level} - "
    "[{extra[request_id]}] [{extra[user_id]}] [{extra[agent_id]}] - {message}"
)
_DEFAULT_CONSOLE_FORMAT = "{level} - {message}"
_sink_ids_by_key: dict[str, list[int]] = {}


def _remove_configured_sinks(sink_key: str) -> None:
    for sink_id in _sink_ids_by_key.pop(sink_key, []):
        loguru_logger.remove(sink_id)


def _sink_filter(logger_names: tuple[str, ...]):
    def should_log(record: dict[str, Any]) -> bool:
        logger_name = record["extra"].get("logger_name", record["name"])
        return any(
            logger_name == name or logger_name.startswith(f"{name}.")
            for name in logger_names
        )

    return should_log


class InterceptHandler(logging.Handler):
    """Route standard-library logging records into loguru sinks."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        loguru_logger.bind(logger_name=record.name, **get_log_context()).opt(
            depth=depth,
            exception=record.exc_info,
        ).log(level, record.getMessage())


def configure_loguru_logging(
    *,
    logger_names: Iterable[str],
    sink_key: str,
    level: str = "INFO",
    log_file: str | None = None,
    log_format: str | None = _DEFAULT_TEXT_FORMAT,
    rotation: str | None = None,
    retention: int | str | None = None,
    compression: str | None = None,
    console_enabled: bool = False,
    console_level: str | None = None,
    console_format: str | None = _DEFAULT_CONSOLE_FORMAT,
    console_sink: Any = sys.stderr,
    default_file_format: str = _DEFAULT_TEXT_FORMAT,
    default_console_format: str = _DEFAULT_CONSOLE_FORMAT,
    force: bool = False,
) -> bool:
    """
    Configure loguru sinks and bridge named stdlib logger namespaces.
    """
    names = tuple(logger_names)
    if not names:
        return False

    if sink_key in _sink_ids_by_key and not force:
        return False

    try:
        loguru_logger.remove(0)
    except ValueError:
        pass
    _remove_configured_sinks(sink_key)

    active_filter = _sink_filter(names)
    normalized_level = (level or "INFO").upper()
    sink_ids: list[int] = []
    file_format = (log_format or "").strip()
    console_template = (console_format or "").strip()

    if log_file:
        file_template = (
            default_file_format
            if file_format.lower() in {"", "json", "text"}
            else file_format
        )
        try:
            sink_ids.append(
                loguru_logger.add(
                    log_file,
                    level=normalized_level,
                    format=file_template,
                    filter=active_filter,
                    rotation=rotation,
                    retention=retention,
                    compression=compression,
                    encoding="utf-8",
                    enqueue=False,
                    serialize=file_format.lower() == "json",
                )
            )
        except Exception as exc:
            print(f"Warning: Failed to setup file logging: {exc}", file=sys.stderr)

    if console_enabled:
        console_template = (
            default_console_format
            if console_template.lower() in {"", "json", "text"}
            else console_template
        )
        sink_ids.append(
            loguru_logger.add(
                console_sink,
                level=(console_level or normalized_level).upper(),
                format=console_template,
                filter=active_filter,
                enqueue=False,
                serialize=(console_format or "").strip().lower() == "json",
            )
        )

    if not sink_ids:
        return False

    for logger_name in names:
        stdlib_logger = logging.getLogger(logger_name)
        for handler in list(stdlib_logger.handlers):
            stdlib_logger.removeHandler(handler)
            handler.close()
        stdlib_logger.addHandler(InterceptHandler())
        stdlib_logger.setLevel(normalized_level)
        stdlib_logger.propagate = False

    _sink_ids_by_key[sink_key] = sink_ids
    return True


def setup_powermem_logging(*, force: bool = False) -> bool:
    """
    Wire ``LOGGING_*`` settings to the ``powermem`` logger namespace.
    """
    try:
        from powermem.config_loader import LoggingSettings
    except Exception as exc:
        print(f"Warning: powermem logging setup skipped: {exc}", file=sys.stderr)
        return False

    settings = LoggingSettings()
    configured = configure_loguru_logging(
        logger_names=("powermem",),
        sink_key="powermem",
        level=settings.level,
        log_file=settings.file,
        log_format=settings.format,
        rotation=settings.max_size,
        retention=settings.backup_count,
        compression="gz" if settings.compress_backups else None,
        console_enabled=settings.console_enabled,
        console_level=settings.console_level,
        console_format=settings.console_format,
        console_sink=sys.stderr,
        force=force,
    )

    if configured:
        logging.getLogger("powermem").debug(
            "PowerMem SDK logging initialized (file=%s)",
            os.path.abspath(settings.file) if settings.file else "<disabled>",
        )

    return configured

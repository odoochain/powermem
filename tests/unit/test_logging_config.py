"""Tests for powermem.logging_config loguru wiring."""

import json
import logging
import os
from io import StringIO

import pytest

from powermem.log_context import (
    TraceContextFilter,
    reset_log_context,
    set_log_context,
)
from powermem.logging_config import configure_loguru_logging, setup_powermem_logging


@pytest.fixture(autouse=True)
def reset_powermem_logging():
    import powermem.logging_config as mod

    mod._remove_configured_sinks("powermem")
    logging.getLogger("powermem").handlers.clear()
    yield
    mod._remove_configured_sinks("powermem")
    logging.getLogger("powermem").handlers.clear()


def test_setup_powermem_logging_writes_to_file(tmp_path, monkeypatch):
    log_file = str(tmp_path / "test.log")
    monkeypatch.setenv("LOGGING_FILE", log_file)
    monkeypatch.setenv("LOGGING_LEVEL", "DEBUG")
    monkeypatch.setenv("LOGGING_CONSOLE_ENABLED", "false")

    assert setup_powermem_logging(force=True) is True
    assert os.path.exists(log_file)

    test_logger = logging.getLogger("powermem.test_logging_config")
    test_logger.debug("hello from test")

    with open(log_file) as f:
        content = f.read()
    assert "PowerMem SDK logging initialized" in content
    assert "hello from test" in content


def test_setup_powermem_logging_idempotent(tmp_path, monkeypatch):
    log_file = str(tmp_path / "test.log")
    monkeypatch.setenv("LOGGING_FILE", log_file)
    monkeypatch.setenv("LOGGING_CONSOLE_ENABLED", "false")

    assert setup_powermem_logging(force=True) is True
    assert setup_powermem_logging() is False


def test_setup_powermem_logging_uses_loguru_format(tmp_path, monkeypatch):
    log_file = str(tmp_path / "format.log")
    monkeypatch.setenv("LOGGING_FILE", log_file)
    monkeypatch.setenv("LOGGING_LEVEL", "INFO")
    monkeypatch.setenv("LOGGING_CONSOLE_ENABLED", "false")
    monkeypatch.setenv(
        "LOGGING_FORMAT",
        "{level} | {extra[logger_name]} | {extra[request_id]} | {message}",
    )

    tokens = set_log_context(request_id="req-from-format-test")
    try:
        assert setup_powermem_logging(force=True) is True
        logging.getLogger("powermem.format_test").info("format check")

        with open(log_file) as f:
            content = f.read()
        assert (
            "INFO | powermem.format_test | req-from-format-test | format check"
            in content
        )
    finally:
        reset_log_context(tokens)


def test_setup_powermem_logging_uses_loguru_rotation_and_compression(
    tmp_path, monkeypatch
):
    log_file = str(tmp_path / "rotate.log")
    monkeypatch.setenv("LOGGING_FILE", log_file)
    monkeypatch.setenv("LOGGING_LEVEL", "DEBUG")
    monkeypatch.setenv("LOGGING_MAX_SIZE", "1 KB")
    monkeypatch.setenv("LOGGING_BACKUP_COUNT", "2")
    monkeypatch.setenv("LOGGING_COMPRESS_BACKUPS", "true")
    monkeypatch.setenv("LOGGING_CONSOLE_ENABLED", "false")

    assert setup_powermem_logging(force=True) is True

    test_logger = logging.getLogger("powermem.rotate_test")
    for i in range(120):
        test_logger.debug("line %d padding padding padding padding", i)

    gz_files = [name for name in os.listdir(tmp_path) if name.endswith(".gz")]
    assert gz_files, "Expected loguru to gzip rotated backups"
    assert len(gz_files) <= 2


def test_json_file_format_does_not_force_console_json(tmp_path):
    log_file = str(tmp_path / "json.log")
    console = StringIO()

    try:
        assert (
            configure_loguru_logging(
                logger_names=("powermem",),
                sink_key="mixed-json",
                level="INFO",
                log_file=log_file,
                log_format="json",
                rotation="100 MB",
                retention=1,
                compression=None,
                console_enabled=True,
                console_format="{level}:{message}",
                console_sink=console,
                force=True,
            )
            is True
        )

        logging.getLogger("powermem.json_test").info("json file, text console")

        file_record = json.loads(open(log_file).read())
        assert sorted(file_record.keys()) == ["record", "text"]
        assert file_record["record"]["message"] == "json file, text console"
        assert console.getvalue().strip() == "INFO:json file, text console"
    finally:
        import powermem.logging_config as mod

        mod._remove_configured_sinks("mixed-json")
        logging.getLogger("powermem").handlers.clear()


def test_text_marker_uses_call_site_default_file_format(tmp_path):
    log_file = str(tmp_path / "server-text.log")

    try:
        assert (
            configure_loguru_logging(
                logger_names=("server",),
                sink_key="server-text",
                level="INFO",
                log_file=log_file,
                log_format="text",
                default_file_format="{level:>7} {extra[logger_name]}: {message}",
                console_enabled=False,
                force=True,
            )
            is True
        )

        logging.getLogger("server").info("server format")

        with open(log_file) as f:
            content = f.read()
        assert "   INFO server: server format" in content
    finally:
        import powermem.logging_config as mod

        mod._remove_configured_sinks("server-text")
        logging.getLogger("server").handlers.clear()


def test_trace_filter_injects_fields(tmp_path):
    log_file = str(tmp_path / "trace.log")
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(message)s [%(request_id)s] [%(user_id)s] [%(agent_id)s]")
    )
    handler.addFilter(TraceContextFilter())

    test_logger = logging.getLogger("powermem.trace_test")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)

    tokens = set_log_context(
        request_id="aaaa-bbbb",
        user_id="user-42",
        agent_id="agent-7",
    )
    try:
        test_logger.debug("hello")
        handler.flush()

        with open(log_file) as f:
            content = f.read()
        assert "[aaaa-bbbb]" in content
        assert "[user-42]" in content
        assert "[agent-7]" in content
    finally:
        reset_log_context(tokens)
        test_logger.removeHandler(handler)
        handler.close()


def test_trace_filter_zero_uuid_default(tmp_path):
    log_file = str(tmp_path / "default.log")
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(message)s [%(request_id)s] [%(user_id)s] [%(agent_id)s]")
    )
    handler.addFilter(TraceContextFilter())

    test_logger = logging.getLogger("powermem.default_test")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)

    try:
        test_logger.debug("no context")
        handler.flush()

        with open(log_file) as f:
            content = f.read()
        zero = "00000000-0000-0000-0000-000000000000"
        assert f"[{zero}]" in content
        assert "[] []" in content
    finally:
        test_logger.removeHandler(handler)
        handler.close()


def test_reset_log_context_restores_previous():
    tokens_outer = set_log_context(request_id="outer-id")
    try:
        tokens_inner = set_log_context(request_id="inner-id")
        from powermem.log_context import _request_id_var

        assert _request_id_var.get() == "inner-id"
        reset_log_context(tokens_inner)
        assert _request_id_var.get() == "outer-id"
    finally:
        reset_log_context(tokens_outer)

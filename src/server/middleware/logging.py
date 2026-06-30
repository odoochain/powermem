"""
Logging middleware for PowerMem API
"""

import logging
import re
import sys
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from powermem.logging_config import configure_loguru_logging

from ..config import config
from ..models.errors import APIError
from ..utils.metrics import get_metrics_collector

# Setup logger
logger = logging.getLogger("server")


def setup_logging():
    """
    Set up server logging.

    This function can be safely called multiple times. It reconfigures the
    server-owned loguru sinks and stdlib logger bridges on each call.
    """
    server_text_format = config.log_console_format
    console_format = (
        config.log_format if config.log_format == "json" else server_text_format
    )
    configure_loguru_logging(
        logger_names=("server", "uvicorn", "uvicorn.error", "uvicorn.access"),
        sink_key="server",
        level=config.log_level,
        log_file=config.log_file,
        log_format=config.log_format,
        rotation=config.log_max_size,
        retention=config.log_backup_count,
        compression="gz" if config.log_compress_backups else None,
        console_enabled=True,
        console_format=console_format,
        console_sink=sys.stdout,
        default_file_format=server_text_format,
        default_console_format=server_text_format,
        force=True,
    )

    try:
        from powermem.logging_config import setup_powermem_logging

        setup_powermem_logging()
    except Exception as e:
        print(f"Warning: Failed to setup powermem SDK logging: {e}", file=sys.stderr)


_USER_PATH_RE = re.compile(r"/users/([^/]+)")
_AGENT_PATH_RE = re.compile(r"/agents/([^/]+)")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging"""

    @staticmethod
    def _extract_trace_ids(request: Request) -> tuple:
        user_id = request.query_params.get("user_id", "")
        if not user_id:
            m = _USER_PATH_RE.search(request.url.path)
            if m:
                user_id = m.group(1)

        agent_id = request.query_params.get("agent_id", "")
        if not agent_id:
            m = _AGENT_PATH_RE.search(request.url.path)
            if m:
                agent_id = m.group(1)

        return user_id or "", agent_id or ""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Propagate trace context to SDK logger tree
        from powermem.log_context import set_log_context, reset_log_context

        user_id, agent_id = self._extract_trace_ids(request)
        tokens = set_log_context(
            request_id=request_id,
            user_id=user_id,
            agent_id=agent_id,
        )

        # Start time
        start_time = time.time()

        # Log request
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Record metrics
            metrics_collector = get_metrics_collector()
            # Normalize path to endpoint
            endpoint = metrics_collector.normalize_endpoint(request.url.path)
            metrics_collector.record_api_request(
                method=request.method,
                endpoint=endpoint,
                status_code=response.status_code,
                duration=duration,
            )

            # Log response
            logger.info(
                f"{request.method} {request.url.path} - {response.status_code}",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": duration * 1000,
                },
            )

            # Add request ID to response header
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration = time.time() - start_time

            # Determine status code and whether this is an expected error
            status_code = 500
            is_expected_error = False

            if isinstance(e, APIError):
                status_code = e.status_code
                # Client errors (4xx) are expected, server errors (5xx) are unexpected
                is_expected_error = status_code < 500

            # Record metrics for error
            metrics_collector = get_metrics_collector()
            endpoint = metrics_collector.normalize_endpoint(request.url.path)
            metrics_collector.record_api_request(
                method=request.method,
                endpoint=endpoint,
                status_code=status_code,
                duration=duration,
            )

            # For expected errors (4xx), log without stack trace
            # For unexpected errors (5xx), log with full stack trace
            if is_expected_error:
                logger.warning(
                    f"{request.method} {request.url.path} - {status_code}: {str(e)}",
                    extra={
                        "request_id": request_id,
                        "status_code": status_code,
                        "error": str(e),
                        "duration_ms": duration * 1000,
                    },
                )
            else:
                logger.error(
                    f"Error processing {request.method} {request.url.path}",
                    extra={
                        "request_id": request_id,
                        "status_code": status_code,
                        "error": str(e),
                        "duration_ms": duration * 1000,
                    },
                    exc_info=True,
                )
            raise
        finally:
            reset_log_context(tokens)


def log_request(request: Request, message: str, **kwargs):
    """
    Log a request with additional context.

    Args:
        request: FastAPI request object
        message: Log message
        **kwargs: Additional context
    """
    extra = {"request_id": getattr(request.state, "request_id", None), **kwargs}
    logger.info(message, extra=extra)

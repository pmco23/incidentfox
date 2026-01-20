"""
Production-grade structured logging with OpenTelemetry integration.

Features:
- Structured JSON logging
- Correlation IDs for request tracing
- Integration with OpenTelemetry
- CloudWatch and local file output
- Performance logging
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, Processor

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False

from .config import LoggingConfig

# Context variable for correlation ID
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Get or create correlation ID for current context."""
    corr_id = correlation_id_var.get()
    if corr_id is None:
        corr_id = str(uuid.uuid4())
        correlation_id_var.set(corr_id)
    return corr_id


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context."""
    correlation_id_var.set(correlation_id)


def add_correlation_id(
    logger: Any, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add correlation ID to log event."""
    corr_id = correlation_id_var.get()
    if corr_id:
        event_dict["correlation_id"] = corr_id
    return event_dict


def add_trace_context(
    logger: Any, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add OpenTelemetry trace context to log event."""
    if HAS_OTEL:
        span = trace.get_current_span()
        if span.is_recording():
            span_context = span.get_span_context()
            event_dict["trace_id"] = format(span_context.trace_id, "032x")
            event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


def add_severity(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add severity level for CloudWatch compatibility."""
    level = event_dict.get("level", "").upper()
    severity_map = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }
    event_dict["severity"] = severity_map.get(level, "INFO")
    return event_dict


def setup_logging(config: LoggingConfig, service_name: str = "ai-agent") -> None:
    """
    Setup structured logging with OpenTelemetry integration.

    Args:
        config: Logging configuration
        service_name: Service name for traces and logs
    """
    # Setup OpenTelemetry if available
    if HAS_OTEL:
        resource = Resource(attributes={SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        # Add span processors
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        # Add OTLP exporter if endpoint is configured
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
            )

        trace.set_tracer_provider(provider)

    # Configure structlog processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Add custom processors
    if config.enable_correlation_ids:
        processors.append(add_correlation_id)

    processors.append(add_trace_context)
    processors.append(add_severity)

    # Add final formatter
    if config.format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, config.level),
    )

    # Suppress noisy loggers
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("kubernetes").setLevel(logging.WARNING)

    logger = structlog.get_logger(__name__)
    logger.info(
        "logging_configured",
        level=config.level,
        format=config.format,
        correlation_ids=config.enable_correlation_ids,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structured logger
    """
    return structlog.get_logger(name)


# Performance logging decorator
import functools
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def log_performance(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to log function performance metrics.

    Usage:
        @log_performance
        def my_function():
            ...
    """

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> T:
        logger = get_logger(func.__module__)
        start_time = time.perf_counter()

        try:
            result = await func(*args, **kwargs)
            duration = time.perf_counter() - start_time

            logger.info(
                "function_completed",
                function=func.__name__,
                duration_seconds=round(duration, 3),
                success=True,
            )
            return result

        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                "function_failed",
                function=func.__name__,
                duration_seconds=round(duration, 3),
                error=str(e),
                exc_info=True,
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> T:
        logger = get_logger(func.__module__)
        start_time = time.perf_counter()

        try:
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start_time

            logger.info(
                "function_completed",
                function=func.__name__,
                duration_seconds=round(duration, 3),
                success=True,
            )
            return result

        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                "function_failed",
                function=func.__name__,
                duration_seconds=round(duration, 3),
                error=str(e),
                exc_info=True,
            )
            raise

    # Return appropriate wrapper based on function type
    import inspect

    if inspect.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    else:
        return sync_wrapper  # type: ignore


import os

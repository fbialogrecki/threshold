import logging
import os
from collections.abc import Mapping
from typing import Any

import structlog

SENSITIVE_KEYS = {
    "authorization",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "password",
    "client_secret",
    "payload_key",
    "cookie",
    "cookies",
    "set-cookie",
    "headers",
    "body",
    "email",
    "exact_address",
    "location_payload",
}


class OtelLogDefaultsFilter(logging.Filter):
    """Populate OTel formatter fields, even before auto log instrumentation is active."""

    def filter(self, record: logging.LogRecord) -> bool:
        trace_id = "0"
        span_id = "0"
        trace_sampled = False
        try:
            from opentelemetry import trace

            span_context = trace.get_current_span().get_span_context()
            if span_context.is_valid:
                trace_id = f"{span_context.trace_id:032x}"
                span_id = f"{span_context.span_id:016x}"
                trace_sampled = span_context.trace_flags.sampled
        except Exception:  # pragma: no cover - logging must never break app startup
            pass

        service_name = (
            os.getenv("OTEL_SERVICE_NAME")
            or os.getenv("THRESHOLD_SERVICE_NAME")
            or "unknown_service"
        )
        try:
            from threshold_common.http_observability import request_id_context

            request_id = request_id_context.get()
        except Exception:  # pragma: no cover - logging must never break app startup
            request_id = "-"

        error_type = "-"
        if record.exc_info is not None:
            exception_type = record.exc_info[0]
            if exception_type is not None:
                error_type = exception_type.__name__
            record.exc_info = None
            record.exc_text = None

        for key in SENSITIVE_KEYS:
            if key in record.__dict__:
                record.__dict__[key] = "[REDACTED]"

        for field, default in {
            "otelTraceID": trace_id,
            "otelSpanID": span_id,
            "otelServiceName": service_name,
            "otelTraceSampled": trace_sampled,
            "requestID": request_id,
            "errorType": error_type,
        }.items():
            if not hasattr(record, field) or getattr(record, field) in {None, "", "0"}:
                setattr(record, field, default)
        return True


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        if key.lower() in SENSITIVE_KEYS:
            redacted[key] = "[REDACTED]"
        elif isinstance(value, Mapping):
            redacted[key] = redact_mapping(value)
        else:
            redacted[key] = value
    return redacted


def configure_logging() -> None:
    """Configure application logging for local and Kubernetes runtimes."""
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] "
            "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s "
            "request_id=%(requestID)s error_type=%(errorType)s "
            "resource.service.name=%(otelServiceName)s "
            "trace_sampled=%(otelTraceSampled)s] - %(message)s"
        ),
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(OtelLogDefaultsFilter())
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

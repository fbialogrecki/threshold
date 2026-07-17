import logging
import sys
from contextvars import Token

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, TraceState
from pytest import MonkeyPatch

from threshold_common.http_observability import request_id_context
from threshold_common.logging import OtelLogDefaultsFilter, redact_mapping

TRACE_ID = 0xABCDEF1234567890ABCDEF1234567890
SPAN_ID = 0x1234567890ABCDEF


def _attach_sample_span() -> Token[Context]:
    span_context = SpanContext(
        trace_id=TRACE_ID,
        span_id=SPAN_ID,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )
    return otel_context.attach(trace.set_span_in_context(NonRecordingSpan(span_context)))


def test_otel_log_defaults_filter_populates_trace_fields_from_current_span(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_SERVICE_NAME", "test-service")
    token = _attach_sample_span()
    try:
        record = logging.LogRecord(
            name="threshold.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        assert OtelLogDefaultsFilter().filter(record)
    finally:
        otel_context.detach(token)

    assert record.__dict__["otelTraceID"] == "abcdef1234567890abcdef1234567890"
    assert record.__dict__["otelSpanID"] == "1234567890abcdef"
    assert record.__dict__["otelServiceName"] == "test-service"
    assert record.__dict__["otelTraceSampled"] is True


def test_log_filter_correlates_request_and_removes_raw_exception() -> None:
    request_token = request_id_context.set("req-123")
    try:
        try:
            raise RuntimeError("private raw exception text")
        except RuntimeError:
            record = logging.LogRecord(
                name="threshold.test",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="operation failed",
                args=(),
                exc_info=sys.exc_info(),
            )
        assert OtelLogDefaultsFilter().filter(record)
    finally:
        request_id_context.reset(request_token)

    assert record.__dict__["requestID"] == "req-123"
    assert record.__dict__["errorType"] == "RuntimeError"
    assert record.exc_info is None
    assert record.exc_text is None
    assert "private raw exception text" not in repr(record.__dict__)


def test_redaction_covers_auth_cookies_body_email_and_nested_tokens() -> None:
    values = {
        "authorization": "private-auth",
        "cookie": "private-cookie",
        "body": "private-body",
        "email": "private@example.test",
        "nested": {"refresh_token": "private-token"},
        "safe": "kept",
    }

    redacted = redact_mapping(values)

    assert redacted == {
        "authorization": "[REDACTED]",
        "cookie": "[REDACTED]",
        "body": "[REDACTED]",
        "email": "[REDACTED]",
        "nested": {"refresh_token": "[REDACTED]"},
        "safe": "kept",
    }

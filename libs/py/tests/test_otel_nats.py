from contextvars import Token

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, TraceState

import otel_nats
from threshold_common.otel_nats import (
    decode_traced_json_payload,
    encode_traced_json_payload,
    extract_traceparent,
    inject_traceparent,
)

TRACE_ID = 0x1234567890ABCDEF1234567890ABCDEF
SPAN_ID = 0x1234567890ABCDEF
TRACEPARENT = "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01"


def _attach_sample_span() -> Token[Context]:
    span_context = SpanContext(
        trace_id=TRACE_ID,
        span_id=SPAN_ID,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )
    return otel_context.attach(trace.set_span_in_context(NonRecordingSpan(span_context)))


def test_inject_traceparent_adds_active_w3c_context_and_preserves_headers() -> None:
    token = _attach_sample_span()
    try:
        headers = inject_traceparent({"x-request-id": "req-1"})
    finally:
        otel_context.detach(token)

    assert headers["x-request-id"] == "req-1"
    assert headers["traceparent"] == TRACEPARENT


def test_extract_traceparent_returns_context_with_remote_parent() -> None:
    context = extract_traceparent({"traceparent": TRACEPARENT})

    span_context = trace.get_current_span(context).get_span_context()

    assert span_context.is_valid
    assert span_context.is_remote
    assert span_context.trace_id == TRACE_ID
    assert span_context.span_id == SPAN_ID


def test_traced_json_payload_round_trip_preserves_payload_and_context() -> None:
    payload = {"authentik_subject": "ak-subject", "email": "trace@example.test"}
    token = _attach_sample_span()
    try:
        encoded = encode_traced_json_payload(payload)
    finally:
        otel_context.detach(token)

    decoded, context = decode_traced_json_payload(encoded)
    span_context = trace.get_current_span(context).get_span_context()

    assert decoded == payload
    assert span_context.trace_id == TRACE_ID
    assert span_context.span_id == SPAN_ID


def test_empty_or_legacy_headers_extract_to_invalid_context() -> None:
    context = extract_traceparent(None)

    span_context = trace.get_current_span(context).get_span_context()

    assert not span_context.is_valid


def test_top_level_otel_nats_module_re_exports_helpers() -> None:
    assert otel_nats.inject_traceparent is inject_traceparent
    assert otel_nats.extract_traceparent is extract_traceparent

import json
from collections.abc import Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import propagate, trace
from opentelemetry.context import Context
from opentelemetry.trace import SpanKind


def inject_traceparent(headers: MutableMapping[str, str] | None = None) -> dict[str, str]:
    """Return NATS headers with the active W3C trace context injected."""
    carrier: dict[str, str] = dict(headers or {})
    propagate.inject(carrier)
    return carrier


def extract_traceparent(headers: Mapping[str, str] | None) -> Context:
    """Extract W3C trace context from NATS headers."""
    return propagate.extract(dict(headers or {}))


inject_trace_context = inject_traceparent
extract_trace_context = extract_traceparent


@contextmanager
def nats_consumer_span(
    *,
    subject: str,
    headers: Mapping[str, str] | None,
    span_name: str | None = None,
) -> Iterator[trace.Span]:
    """Start a NATS consumer span using trace context extracted from headers."""
    tracer = trace.get_tracer(__name__)
    context = extract_traceparent(headers)
    with tracer.start_as_current_span(
        span_name or f"NATS {subject} receive",
        context=context,
        kind=SpanKind.CONSUMER,
        attributes={
            "messaging.system": "nats",
            "messaging.destination.name": subject,
        },
    ) as span:
        yield span


def get_message_headers(message: Any) -> Mapping[str, str] | None:
    """Return NATS message headers without tying callers to nats-py internals."""
    headers = getattr(message, "headers", None)
    if headers is None:
        return None
    return dict(headers)


def encode_traced_json_payload(payload: Mapping[str, Any]) -> bytes:
    """Encode a JSON payload with trace headers for transports without NATS headers."""
    envelope = {
        "payload": dict(payload),
        "headers": inject_traceparent(),
    }
    return json.dumps(envelope).encode("utf-8")


def decode_traced_json_payload(data: bytes) -> tuple[dict[str, Any], Context]:
    """Decode traced JSON envelope, with legacy raw-payload fallback."""
    decoded = json.loads(data.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("NATS JSON payload must be an object")

    maybe_payload = decoded.get("payload")
    maybe_headers = decoded.get("headers")
    if isinstance(maybe_payload, dict) and isinstance(maybe_headers, dict):
        return maybe_payload, extract_traceparent(maybe_headers)

    return decoded, extract_traceparent(None)

import logging
import os

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)
_configured = False
_client_instrumented = False


def configure_telemetry(service_name: str) -> None:
    """Configure OpenTelemetry tracing for a Threshold service.

    The OTLP exporter follows standard OTEL_* environment variables. In Kubernetes we point
    OTEL_EXPORTER_OTLP_ENDPOINT at the in-cluster collector; locally the SDK default is fine.
    """
    global _configured, _client_instrumented

    if _configured:
        return

    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    os.environ.setdefault("OTEL_RESOURCE_ATTRIBUTES", f"service.name={service_name}")

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    sdk_enabled = os.getenv("OTEL_SDK_DISABLED", "").lower() not in {"true", "1", "yes"}
    if sdk_enabled and os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
        metrics.set_meter_provider(
            MeterProvider(resource=resource, metric_readers=[metric_reader])
        )

    if not _client_instrumented:
        _instrument_optional_client(
            module_name="opentelemetry.instrumentation.httpx",
            class_name="HTTPXClientInstrumentor",
            client_name="HTTPX",
        )
        _instrument_optional_client(
            module_name="opentelemetry.instrumentation.asyncpg",
            class_name="AsyncPGInstrumentor",
            client_name="asyncpg",
        )
        _instrument_optional_client(
            module_name="opentelemetry.instrumentation.psycopg",
            class_name="PsycopgInstrumentor",
            client_name="psycopg",
        )
        LoggingInstrumentor().instrument(set_logging_format=False)
        _client_instrumented = True

    _configured = True
    logger.info("OpenTelemetry tracing configured", extra={"service_name": service_name})


def _instrument_optional_client(*, module_name: str, class_name: str, client_name: str) -> None:
    try:
        module = __import__(module_name, fromlist=[class_name])
    except ModuleNotFoundError:
        logger.debug("%s is not installed; skipping OpenTelemetry instrumentation", client_name)
        return

    instrumentor_factory = getattr(module, class_name)
    instrumentor_factory().instrument()


def instrument_fastapi(app: FastAPI) -> None:
    """Attach FastAPI route instrumentation to an app instance."""
    FastAPIInstrumentor.instrument_app(app)

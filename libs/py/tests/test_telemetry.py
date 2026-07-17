import importlib
import sys
import types
from typing import Any

from fastapi import FastAPI
from opentelemetry.metrics import NoOpMeterProvider
from pytest import MonkeyPatch


def test_configure_telemetry_instruments_http_and_database_clients(
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakeInstrumentor:
        def __init__(self, name: str) -> None:
            self.name = name

        def instrument(self, **_: object) -> None:
            calls.append(self.name)

    def module_with_instrumentor(class_name: str, name: str) -> types.ModuleType:
        module = types.ModuleType(class_name)
        setattr(module, class_name, lambda: FakeInstrumentor(name))
        return module

    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.instrumentation.httpx",
        module_with_instrumentor("HTTPXClientInstrumentor", "httpx"),
    )
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.instrumentation.asyncpg",
        module_with_instrumentor("AsyncPGInstrumentor", "asyncpg"),
    )
    monkeypatch.setitem(
        sys.modules,
        "opentelemetry.instrumentation.psycopg",
        module_with_instrumentor("PsycopgInstrumentor", "psycopg"),
    )

    telemetry = importlib.import_module("threshold_common.telemetry")
    telemetry = importlib.reload(telemetry)

    telemetry.configure_telemetry("test-service")

    assert calls == ["httpx", "asyncpg", "psycopg"]


def test_configure_telemetry_exports_metrics_over_existing_otlp_pipeline(
    monkeypatch: MonkeyPatch,
) -> None:
    telemetry = importlib.import_module("threshold_common.telemetry")
    telemetry = importlib.reload(telemetry)
    configured: dict[str, object] = {}

    class FakeExporter:
        pass

    class FakeReader:
        def __init__(self, exporter: object) -> None:
            configured["exporter"] = exporter

    class FakeMeterProvider:
        def __init__(self, *, resource: object, metric_readers: list[object]) -> None:
            configured["resource"] = resource
            configured["readers"] = metric_readers

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
    monkeypatch.setattr(telemetry, "OTLPMetricExporter", FakeExporter, raising=False)
    monkeypatch.setattr(telemetry, "PeriodicExportingMetricReader", FakeReader, raising=False)
    monkeypatch.setattr(telemetry, "MeterProvider", FakeMeterProvider, raising=False)
    monkeypatch.setattr(
        telemetry.metrics,
        "set_meter_provider",
        lambda provider: configured.setdefault("provider", provider),
    )

    telemetry.configure_telemetry("test-service")

    assert isinstance(configured["exporter"], FakeExporter)
    assert configured["readers"]
    assert configured["provider"] is not None


def test_instrument_fastapi_keeps_tracing_but_uses_noop_metrics_provider(
    monkeypatch: MonkeyPatch,
) -> None:
    telemetry = importlib.import_module("threshold_common.telemetry")
    telemetry = importlib.reload(telemetry)
    captured: dict[str, Any] = {}

    def fake_instrument_app(app: FastAPI, **kwargs: Any) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(telemetry.FastAPIInstrumentor, "instrument_app", fake_instrument_app)
    app = FastAPI()

    telemetry.instrument_fastapi(app)

    assert captured["app"] is app
    assert isinstance(captured["meter_provider"], NoOpMeterProvider)
    assert "tracer_provider" not in captured

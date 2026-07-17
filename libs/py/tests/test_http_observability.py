import logging
from collections.abc import Iterable
from typing import Any, cast

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, Metric

from threshold_common.http_observability import (
    HttpObservabilityMiddleware,
    instrument_http_observability,
)


def _metrics(reader: InMemoryMetricReader) -> Iterable[Metric]:
    data = reader.get_metrics_data()
    assert data is not None
    for resource_metric in data.resource_metrics:
        for scope_metric in resource_metric.scope_metrics:
            yield from scope_metric.metrics


def test_installs_shared_http_observability_middleware() -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    app = FastAPI()

    instrument_http_observability(
        app,
        service_name="test-service",
        meter=provider.get_meter("test-install"),
    )

    assert len(app.user_middleware) == 1
    assert cast(Any, app.user_middleware[0].cls) is HttpObservabilityMiddleware


def test_records_normalized_route_request_count_and_latency() -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    app = FastAPI()
    app.add_middleware(
        HttpObservabilityMiddleware,
        service_name="test-service",
        meter=provider.get_meter("test"),
    )

    @app.get("/widgets/{widget_id}")
    def widget(widget_id: str) -> dict[str, str]:
        return {"widget_id": widget_id}

    with TestClient(app) as client:
        assert client.get("/widgets/private-user-value").status_code == 200

    by_name = {metric.name: metric for metric in _metrics(reader)}
    assert set(by_name) == {
        "threshold.http.server.requests",
        "threshold.http.server.request.duration",
        "threshold.http.server.errors",
    }
    request_point = cast(Any, by_name["threshold.http.server.requests"].data.data_points[0])
    duration_point = cast(
        Any, by_name["threshold.http.server.request.duration"].data.data_points[0]
    )
    expected = {
        "http.request.method": "GET",
        "http.route": "/widgets/{widget_id}",
        "http.response.status_class": "2xx",
        "service.name": "test-service",
    }
    assert dict(request_point.attributes) == expected
    assert dict(duration_point.attributes) == expected
    assert request_point.value == 1
    assert duration_point.count == 1
    assert "private-user-value" not in repr(by_name)


def test_uses_explicit_fallback_route_and_bounded_error_labels() -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    app = FastAPI()
    app.add_middleware(
        HttpObservabilityMiddleware,
        service_name="test-service",
        meter=provider.get_meter("test-fallback"),
    )

    @app.get("/broken/{item_id}")
    def broken(item_id: str) -> Response:
        return Response(status_code=503)

    with TestClient(app) as client:
        assert client.get("/contains/private-value").status_code == 404
        assert client.get("/broken/private-value").status_code == 503

    errors = next(
        metric for metric in _metrics(reader) if metric.name == "threshold.http.server.errors"
    )
    points = {
        dict(cast(Any, point).attributes)["http.route"]: cast(Any, point)
        for point in errors.data.data_points
    }
    assert set(points) == {"__unmatched__", "/broken/{item_id}"}
    assert points["__unmatched__"].value == 0
    assert points["/broken/{item_id}"].value == 1
    assert dict(points["/broken/{item_id}"].attributes)["http.response.status_class"] == "5xx"
    assert "private-value" not in repr(errors)


def test_correlates_request_logs_without_sensitive_request_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    app = FastAPI()
    app.add_middleware(
        HttpObservabilityMiddleware,
        service_name="test-service",
        meter=provider.get_meter("test-logging"),
    )

    @app.post("/widgets/{widget_id}")
    def widget(widget_id: str) -> dict[str, str]:
        return {"widget_id": widget_id}

    with caplog.at_level(logging.INFO, logger="threshold.http"), TestClient(app) as client:
        response = client.post(
            "/widgets/private-path?token=private-query",
            headers={
                "x-request-id": "req-safe_123",
                "authorization": "Bearer private-auth",
                "cookie": "session=private-cookie",
            },
            json={"email": "private@example.test", "token": "private-body"},
        )

    assert response.headers["x-request-id"] == "req-safe_123"
    record = cast(Any, next(record for record in caplog.records if record.name == "threshold.http"))
    assert record.request_id == "req-safe_123"
    assert record.http_route == "/widgets/{widget_id}"
    assert record.http_method == "POST"
    assert record.http_status_class == "2xx"
    rendered = repr(record.__dict__)
    for sensitive in (
        "private-path",
        "private-query",
        "private-auth",
        "private-cookie",
        "private@example.test",
        "private-body",
    ):
        assert sensitive not in rendered
    assert record.exc_info is None

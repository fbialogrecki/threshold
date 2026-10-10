import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request, Response
from opentelemetry import metrics
from opentelemetry.metrics import Meter
from starlette.middleware.base import BaseHTTPMiddleware

_STANDARD_METHODS = {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("threshold.http")


def instrument_http_observability(
    app: FastAPI,
    *,
    service_name: str,
    meter: Meter | None = None,
) -> None:
    """Install the shared low-cardinality HTTP metrics and correlation middleware."""
    app.add_middleware(
        HttpObservabilityMiddleware,
        service_name=service_name,
        meter=meter or metrics.get_meter("threshold.http"),
    )


class HttpObservabilityMiddleware(BaseHTTPMiddleware):
    """Record bounded HTTP server metrics without paths, queries, or user data."""

    def __init__(self, app: Any, *, service_name: str, meter: Meter) -> None:
        super().__init__(app)
        self._service_name = service_name
        self._requests = meter.create_counter(
            "threshold.http.server.requests",
            unit="{request}",
            description="Completed HTTP server requests.",
        )
        self._duration = meter.create_histogram(
            "threshold.http.server.request.duration",
            unit="s",
            description="HTTP server request duration in seconds.",
        )
        self._errors = meter.create_counter(
            "threshold.http.server.errors",
            unit="{error}",
            description="HTTP server requests completed with a 5xx response.",
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.perf_counter()
        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = (
            supplied_request_id if _REQUEST_ID.fullmatch(supplied_request_id) else uuid.uuid4().hex
        )
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["x-request-id"] = request_id
        except Exception:
            status_code = 500
            attributes = self._attributes(request, status_code)
            self._record(started, attributes, is_error=True)
            self._log_request(request_id, attributes, failed=True)
            raise
        else:
            attributes = self._attributes(request, status_code)
            self._record(started, attributes, is_error=status_code >= 500)
            self._log_request(request_id, attributes, failed=False)
            return response
        finally:
            request_id_context.reset(token)

    def _record(self, started: float, attributes: dict[str, str], *, is_error: bool) -> None:
        self._requests.add(1, attributes)
        self._duration.record(time.perf_counter() - started, attributes)
        if is_error:
            self._errors.add(1, attributes)

    @staticmethod
    def _log_request(request_id: str, attributes: dict[str, str], *, failed: bool) -> None:
        logger.log(
            logging.ERROR if failed else logging.INFO,
            "HTTP request failed" if failed else "HTTP request completed",
            extra={
                "request_id": request_id,
                "http_method": attributes["http.request.method"],
                "http_route": attributes["http.route"],
                "http_status_class": attributes["http.response.status_class"],
            },
        )

    def _attributes(self, request: Request, status_code: int) -> dict[str, str]:
        route = request.scope.get("route")
        route_template = getattr(route, "path", None)
        if not isinstance(route_template, str):
            route_template = "__unmatched__" if status_code == 404 else "__unresolved__"
        method = request.method if request.method in _STANDARD_METHODS else "OTHER"
        return {
            "http.request.method": method,
            "http.route": route_template,
            "http.response.status_class": f"{status_code // 100}xx",
            "service.name": self._service_name,
        }

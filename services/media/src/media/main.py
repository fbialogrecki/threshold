from fastapi import FastAPI, HTTPException

from media import main_dependencies
from media.api.routes import router
from media.db.readiness import check_database_ready
from media.main_dependencies import create_schema_for_local_sqlite, settings
from threshold_common.health import ok
from threshold_common.http_observability import instrument_http_observability
from threshold_common.logging import configure_logging
from threshold_common.telemetry import configure_telemetry, instrument_fastapi

configure_logging()
configure_telemetry(settings.service_name)
create_schema_for_local_sqlite()

app = FastAPI(title="Threshold media", version="0.1.0")
instrument_fastapi(app)
instrument_http_observability(app, service_name=settings.service_name)
app.include_router(router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return ok(settings.service_name)


@app.get("/readyz")
def readyz() -> dict[str, str]:
    try:
        check_database_ready(main_dependencies.engine)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database is not ready") from exc
    return ok(settings.service_name)

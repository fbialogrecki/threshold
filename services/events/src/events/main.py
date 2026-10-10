from fastapi import FastAPI, HTTPException

from events import main_dependencies
from events.api.routes import router
from events.db.readiness import check_database_ready
from events.main_dependencies import create_schema_for_local_sqlite, settings
from perlimen_common.health import ok
from perlimen_common.http_observability import instrument_http_observability
from perlimen_common.logging import configure_logging
from perlimen_common.telemetry import configure_telemetry, instrument_fastapi

configure_logging()
configure_telemetry(settings.service_name)
create_schema_for_local_sqlite()

app = FastAPI(title="Perlimen events", version="0.1.0")
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

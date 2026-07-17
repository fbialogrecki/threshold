from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from social import main_dependencies
from social.api.routes import router
from social.db.readiness import check_database_ready
from social.main_dependencies import create_schema_for_local_sqlite, settings
from social.nats_server import SocialNatsServer
from threshold_common.health import ok
from threshold_common.http_observability import instrument_http_observability
from threshold_common.logging import configure_logging
from threshold_common.telemetry import configure_telemetry, instrument_fastapi

configure_logging()
configure_telemetry(settings.service_name)
create_schema_for_local_sqlite()

social_nats_server: SocialNatsServer | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global social_nats_server
    if settings.nats_enabled:
        social_nats_server = SocialNatsServer(
            settings=settings,
            session_factory=main_dependencies.session_factory,
        )
        await social_nats_server.start()
    try:
        yield
    finally:
        if social_nats_server is not None:
            await social_nats_server.stop()
            social_nats_server = None


app = FastAPI(title="Threshold social", version="0.1.0", lifespan=lifespan)
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

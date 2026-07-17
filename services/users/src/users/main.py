import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from threshold_common.health import ok
from threshold_common.http_observability import instrument_http_observability
from threshold_common.logging import configure_logging
from threshold_common.telemetry import configure_telemetry, instrument_fastapi
from users import main_dependencies
from users.api.routes import SessionAuthenticationError, _clear_auth_cookies, router
from users.db.readiness import check_database_ready
from users.main_dependencies import create_schema_for_local_sqlite, settings
from users.nats_server import UsersNatsServer

configure_logging()
configure_telemetry(settings.service_name)
create_schema_for_local_sqlite()
logger = logging.getLogger(__name__)
if settings.environment == "production" and not settings.auth_cookie_secure:
    logger.warning(
        "THRESHOLD_AUTH_COOKIE_SECURE is false in production; "
        "only use this behind trusted HTTP/LAN."
    )

nats_server: UsersNatsServer | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global nats_server
    if settings.nats_enabled:
        nats_server = UsersNatsServer(
            nats_url=settings.nats_url,
            subject=settings.users_current_profile_subject,
            list_following_subject=settings.users_list_following_subject,
            session_factory=main_dependencies.session_factory,
        )
        await nats_server.start()
    try:
        yield
    finally:
        if nats_server is not None:
            await nats_server.stop()
            nats_server = None


app = FastAPI(title="Threshold users", version="0.1.1", lifespan=lifespan)
instrument_fastapi(app)
instrument_http_observability(app, service_name=settings.service_name)
app.include_router(router)


@app.exception_handler(SessionAuthenticationError)
def session_authentication_error(
    _: Request, exc: SessionAuthenticationError
) -> JSONResponse:
    response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    _clear_auth_cookies(response)
    return response


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

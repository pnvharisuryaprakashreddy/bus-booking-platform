import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import close_pool, init_pool
from app.errors import DomainError
from app.logging_config import configure_logging, log_event
from app.metrics import metrics
from app.routers import bookings, catalog, health

logger = logging.getLogger("app.access")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_pool(settings.database_url)
    log_event(
        logging.getLogger("app"),
        logging.INFO,
        "service_started",
        version=settings.app_version,
        env=settings.app_env,
    )
    yield
    close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Bus Trip and Seat Reservation API",
        version=settings.app_version,
        summary="Trip search, seat map, reservation and cancellation.",
        description=(
            "Allocated service for the ALGIONS DevOps and Cloud Engineering assessment. "
            "The assessment focus is build, release, deployment and recovery of this API."
        ),
        lifespan=lifespan,
    )

    @application.exception_handler(DomainError)
    async def handle_domain(_request: Request, exc: DomainError) -> JSONResponse:
        log_event(
            logging.getLogger("app"),
            logging.WARNING if exc.status < 500 else logging.ERROR,
            "domain_error",
            error=exc.code,
            status=exc.status,
        )
        return JSONResponse(
            status_code=exc.status,
            content={"error": exc.code, "message": exc.message},
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for err in exc.errors():
            item = {key: value for key, value in err.items() if key != "ctx"}
            ctx = err.get("ctx")
            if isinstance(ctx, dict):
                item["ctx"] = {key: str(value) for key, value in ctx.items()}
            details.append(item)
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "Request validation failed.",
                "details": details,
            },
        )

    @application.middleware("http")
    async def access_log(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                logger,
                logging.ERROR,
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        log_event(
            logger,
            logging.INFO,
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-Id"] = request_id
        metrics.inc("http_requests_total")
        return response

    application.include_router(health.router)
    application.include_router(catalog.router)
    application.include_router(bookings.router)
    return application


app = create_app()

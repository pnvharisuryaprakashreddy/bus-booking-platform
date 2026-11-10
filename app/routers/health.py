import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from psycopg import Connection

from app.config import get_settings
from app.db import get_conn
from app.metrics import metrics
from app.schemas import HealthOut, ReadyOut

router = APIRouter(tags=["operations"])
logger = logging.getLogger("app.health")


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = get_settings()
    return HealthOut(status="ok", service="bus-booking-api", version=settings.app_version)


@router.get("/ready", response_model=ReadyOut)
def ready(conn: Connection = Depends(get_conn)) -> ReadyOut:
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM routes").fetchone()
    except Exception:
        logger.exception("readiness_failed")
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "reason": "database"},
        ) from None
    count = int(row["n"]) if row else 0
    if count < 1:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "reason": "seed_data_missing"},
        )
    return ReadyOut(status="ready", routes=count)


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    return metrics.render()

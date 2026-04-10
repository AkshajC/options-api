from contextlib import asynccontextmanager

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import Base, engine
import app.models.options  # noqa: F401 — registers models with Base
from app.services.snapshot import run_snapshot_job

log = structlog.get_logger(__name__)

Base.metadata.create_all(bind=engine)

_SNAPSHOT_INTERVAL_SECONDS = 60


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_snapshot_job,
        trigger="interval",
        seconds=_SNAPSHOT_INTERVAL_SECONDS,
        id="snapshot_job",
        max_instances=1,  # prevent overlap if a run takes longer than the interval
    )
    scheduler.start()
    log.info("scheduler.started", interval_seconds=_SNAPSHOT_INTERVAL_SECONDS)

    yield

    scheduler.shutdown(wait=False)
    log.info("scheduler.stopped")


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}

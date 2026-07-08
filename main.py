import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as StarletteHTTPException

from config import load_config
from database import init_db, get_readings, delete_old_readings
from collector import Collector
from auth import require_hmac_auth, InvalidApiKey


logger = logging.getLogger(__name__)


def _to_stored(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def retention_loop(db, retention_days):
    while True:
        if retention_days > 0:
            deleted = delete_old_readings(db, retention_days)
            if deleted:
                logger.info("Retention cleanup: removed %d rows older than %d days", deleted, retention_days)
        await asyncio.sleep(86400)


def create_app() -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if hasattr(app.state, "db") and app.state.db is not None:
            yield
        else:
            config = load_config()
            db = init_db(config.db_path)
            app.state.db = db
            app.state.collector_latest = {}

            collector = Collector(config, db)

            task = asyncio.create_task(collector.run())
            app.state.collector_running = True
            app.state.collector_task = task
            app.state.collector_latest = collector.latest_readings
            app.state.start_time = datetime.now(timezone.utc)

            retention_task = asyncio.create_task(retention_loop(db, config.retention_days))

            try:
                yield
            finally:
                task.cancel()
                retention_task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                try:
                    await retention_task
                except asyncio.CancelledError:
                    pass
                db.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(InvalidApiKey)
    async def handle_invalid_api_key(request, exc):
        return JSONResponse(status_code=401, content={"error": "Invalid or missing API key"})

    @app.exception_handler(StarletteHTTPException)
    async def custom_http_exception_handler(request, exc):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})

    @app.get("/api/v1/health")
    async def health():
        collector_latest = getattr(app.state, "collector_latest", {})
        start_time = getattr(app.state, "start_time", None)
        uptime_seconds = 0
        if start_time:
            uptime_seconds = int((datetime.now(timezone.utc) - start_time).total_seconds())

        return {
            "status": "ok",
            "collector_running": getattr(app.state, "collector_running", False),
            "sensors_seen": len(collector_latest),
            "uptime_seconds": uptime_seconds,
        }

    @app.get("/api/v1/sensors")
    async def sensors(_: None = Depends(require_hmac_auth)):
        collector_latest = getattr(app.state, "collector_latest", {})
        sensors_list = []
        for mac, reading in collector_latest.items():
            sensors_list.append({
                "mac": reading.mac,
                "device_name": reading.device_name,
                "sensor_type": reading.sensor_type,
                "last_reading": {
                    "measurements": reading.measurements,
                    "battery": reading.battery,
                    "rssi": reading.rssi,
                    "recorded_at": reading.recorded_at,
                },
            })
        return {"sensors": sensors_list}

    @app.get("/api/v1/readings")
    async def readings(
        mac: str,
        limit: int = 100,
        from_: datetime | None = Query(default=None, alias="from"),
        to: datetime | None = Query(default=None, alias="to"),
        _: None = Depends(require_hmac_auth),
    ):
        if limit > 1000:
            limit = 1000

        collector_latest = getattr(app.state, "collector_latest", {})
        db = app.state.db

        from_ts = _to_stored(from_) if from_ else None
        to_ts = _to_stored(to) if to else None

        rows, has_more = get_readings(db, mac, limit=limit, from_ts=from_ts, to_ts=to_ts)

        if not rows and mac not in collector_latest:
            raise HTTPException(status_code=404, detail={"error": "Unknown sensor", "mac": mac})

        return {
            "mac": mac,
            "count": len(rows),
            "has_more": has_more,
            "readings": [
                {
                    "sensor_type": r["sensor_type"],
                    "measurements": r["measurements"],
                    "battery": r["battery"],
                    "rssi": r["rssi"],
                    "recorded_at": r["recorded_at"],
                }
                for r in rows
            ],
        }

    return app


app = create_app()


if __name__ == "__main__":
    config = load_config()
    kwargs: dict = {"host": config.host, "port": config.port}
    if config.tls_cert and config.tls_key:
        kwargs["ssl_certfile"] = config.tls_cert
        kwargs["ssl_keyfile"] = config.tls_key
    uvicorn.run(app, **kwargs)

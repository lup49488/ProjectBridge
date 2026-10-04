"""FastAPI entry point; fixture-first until session and project APIs land."""

from contextlib import asynccontextmanager
import os
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .api import router as api_router
from .database import connect, initialize_database
from .matching import FORMULA_VERSION

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="ProjectBridge", version="0.1.0", description="Fictional demo for reviewable, complementary student teams", lifespan=lifespan)


def _origin_key(value: str) -> tuple[str, str]:
    parsed = urlsplit(value)
    return parsed.scheme.lower(), parsed.netloc.lower()


@app.middleware("http")
async def verify_browser_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and origin:
        expected = os.getenv("APP_ORIGIN", "http://localhost:5173")
        if _origin_key(origin) != _origin_key(expected):
            return JSONResponse(status_code=403, content={"detail": {"code": "ORIGIN_NOT_ALLOWED", "message": "Request origin is not allowed."}})
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    connection = None
    try:
        connection = connect()
        connection.execute("SELECT 1").fetchone()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="SQLite is unavailable") from exc
    finally:
        if connection is not None:
            connection.close()
    return {"status": "ok", "ai_mode": "fixture", "database": "ready", "formula_version": FORMULA_VERSION}


app.include_router(api_router)

from contextlib import asynccontextmanager
import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import courses, dashboard, exports, health, materials, reset, study_plans, tasks
from app.api.errors import http_exception_handler, validation_exception_handler
from app.config import ensure_runtime_directories, settings
from app.database import SessionLocal, init_db
from app.services.demo_data import ensure_demo_data


logger = logging.getLogger("learning_assistant.api")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_runtime_directories()
    init_db()
    if settings.demo_mode:
        with SessionLocal() as db:
            if ensure_demo_data(db):
                logger.info("demo_data_seeded")
    yield


app = FastAPI(
    title="学伴管家 API",
    description="学习 DDL 与资料管理智能体后端服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_request_id if REQUEST_ID_PATTERN.fullmatch(supplied_request_id) else uuid4().hex[:16]
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    duration_ms = (perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled server exception",
        exc_info=(type(_exc), _exc, _exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误，请稍后重试"}},
    )


app.include_router(health.router)
app.include_router(courses.router)
app.include_router(materials.router)
app.include_router(tasks.router)
app.include_router(dashboard.router)
app.include_router(study_plans.router)
app.include_router(exports.router)
app.include_router(reset.router)

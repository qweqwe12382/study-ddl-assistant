from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic includes the rejected input by default.  Omitting it prevents a
    # malformed password-bearing request from being reflected to the browser or
    # copied into client-side diagnostics.
    safe_errors = [{key: value for key, value in error.items() if key != "input"} for error in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数校验失败",
                "details": jsonable_encoder(safe_errors),
            }
        },
    )


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


async def stale_data_exception_handler(_request: Request, _exc: StaleDataError) -> JSONResponse:
    """Last-resort mapping for an optimistic-lock error raised during flush."""

    return JSONResponse(
        status_code=409,
        content={"error": {"code": "EDIT_CONFLICT", "message": "内容已在其他页面更新，请刷新后再试"}},
    )

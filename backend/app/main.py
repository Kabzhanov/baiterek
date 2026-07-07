import json
import logging
import uuid
from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.api.errors import ApiError
from app.api.router import api_router
from app.db import get_session

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"level": record.levelname, "message": record.getMessage()})

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
app = FastAPI(title="Baiterek API")
app.include_router(api_router, prefix="/api/v1")

def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", None) or uuid.uuid4().hex

@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "details": exc.details, "trace_id": _trace_id(request)},
    )

@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": "invalid_request",
            "message": "Request validation failed",
            "details": {"errors": jsonable_encoder(exc.errors())},
            "trace_id": _trace_id(request),
        },
    )

@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": "http_error", "message": str(exc.detail), "details": {}, "trace_id": _trace_id(request)},
    )

@app.middleware("http")
async def trace_id(request: Request, call_next):
    value = request.headers.get("x-trace-id") or uuid.uuid4().hex
    request.state.trace_id = value
    try:
        response = await call_next(request)
    except Exception:
        logging.exception("request failed")
        return JSONResponse(status_code=500, content={"code":"internal_error","message":"Internal server error","details":{},"trace_id":value})
    response.headers["x-trace-id"] = value
    return response

@app.get("/health/live")
async def live():
    return {"status": "ok"}

@app.get("/health/ready")
async def ready(db: AsyncSession = Depends(get_session)):
    await db.execute(text("select 1"))
    return {"status": "ready"}

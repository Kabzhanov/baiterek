import json, logging, uuid
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"level": record.levelname, "message": record.getMessage()})

handler = logging.StreamHandler(); handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
app = FastAPI(title="Baiterek API")

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
async def live(): return {"status": "ok"}

@app.get("/health/ready")
async def ready(db: AsyncSession = Depends(get_session)):
    await db.execute(text("select 1")); return {"status": "ready"}

import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, http_error_handler
from app.core.logging import configure_logging, request_id_ctx
from app.routers import ai, analytics, attachments, health, kb, tasks, tickets, users

load_dotenv()
configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.allow_dev_create_all:
        from app.database import create_db_and_tables

        create_db_and_tables()
    yield


app = FastAPI(
    title="AI IncidentOps Copilot API",
    description="智维工单：智能运维工单平台",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    request.state.request_id = request_id
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
    except Exception:
        request_id_ctx.reset(token)
        raise
    response.headers["X-Request-Id"] = request_id
    request_id_ctx.reset(token)
    return response


app.include_router(users.router)
app.include_router(tickets.router)
app.include_router(attachments.router)
app.include_router(kb.router)
app.include_router(ai.router)
app.include_router(tasks.router)
app.include_router(analytics.router)
app.include_router(health.router)

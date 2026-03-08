import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.db.repository import init_db
from src.api import applications, admin, webhook
from src.domain.errors import InvalidStateTransitionError, DuplicateApplicationError, WebhookReplayError

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup database on startup
    if not os.path.exists("bree_scoring.db"):
        init_db()
    yield

app = FastAPI(title="Bree Scoring Engine", lifespan=lifespan)

# Setup routers
app.include_router(applications.router)
app.include_router(admin.router)
app.include_router(webhook.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Exception Builders for Domain Errors
@app.exception_handler(InvalidStateTransitionError)
async def invalid_state_transition_handler(request: Request, exc: InvalidStateTransitionError):
    return JSONResponse(
        status_code=400,
        content={"error": "InvalidStateTransitionError", "message": str(exc)}
    )

@app.exception_handler(DuplicateApplicationError)
async def duplicate_application_handler(request: Request, exc: DuplicateApplicationError):
    return JSONResponse(
        status_code=409,
        content={"error": "DuplicateApplicationError", "message": str(exc), "original_application_id": exc.original_application_id}
    )

@app.exception_handler(WebhookReplayError)
async def webhook_replay_handler(request: Request, exc: WebhookReplayError):
    return JSONResponse(
        status_code=400,
        content={"error": "WebhookReplayError", "message": str(exc)}
    )

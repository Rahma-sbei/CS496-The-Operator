"""FastAPI app. The Chrome extension talks only to this."""
from __future__ import annotations

import hmac
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .agent import build_graph
from .runner import RunManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(settings.api_token) < 16:
        raise RuntimeError("Set API_TOKEN (16+ characters) in back/.env before starting the server.")
    app.state.runs = RunManager(build_graph())
    yield


app = FastAPI(title="Gmail Operator", lifespan=lifespan)

# Only the extension may call us from a browser. A random web page cannot: it lacks the
# token header and its origin is not allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^chrome-extension://[a-z]{32}$",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Operator-Token"],
)


def require_token(x_operator_token: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_operator_token, settings.api_token):
        raise HTTPException(status_code=401, detail="Missing or wrong API token. Set it in the extension settings.")


class RunRequest(BaseModel):
    request: str = Field(..., min_length=3, max_length=1000)


class Decision(BaseModel):
    approved: bool


@app.get("/health", dependencies=[Depends(require_token)])
def health():
    from . import gmail_client

    try:
        account = gmail_client.account_email()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Gmail not ready: {e}")
    return {"ok": True, "account": account, "model": settings.openai_model,
            "limits": {"max_steps": settings.max_steps, "max_writes": settings.max_writes}}


@app.post("/runs", dependencies=[Depends(require_token)])
def start_run(body: RunRequest):
    return app.state.runs.start(body.request.strip()).to_dict()


@app.get("/runs/{run_id}", dependencies=[Depends(require_token)])
def get_run(run_id: str):
    try:
        return app.state.runs.get(run_id).to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown run.")


@app.post("/runs/{run_id}/decision", dependencies=[Depends(require_token)])
def decide(run_id: str, body: Decision):
    try:
        return app.state.runs.decide(run_id, body.approved).to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown run.")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

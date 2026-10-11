from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .routers import reference, runs

app = FastAPI(title="ClearMatch", version="1.0.0",
              description="Invoice-to-PO matching with explainable decisions")

# Public demo API, no cookies/auth — open CORS keeps frontend hosting flexible
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(runs.router)
app.include_router(reference.router)


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    if os.environ.get("SEED_ON_START", "1") == "1":
        from sqlalchemy.orm import Session
        from tools.seed_db import seed_if_empty
        seed_if_empty(Session(engine))

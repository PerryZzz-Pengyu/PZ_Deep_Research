from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes
from app.config import ByokCredentialError, get_settings


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await routes.initialize_job_store()
    try:
        yield
    finally:
        await routes.dispose_job_store()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

@app.exception_handler(ByokCredentialError)
async def _byok_credential_error_handler(
    _: Request,
    exc: ByokCredentialError,
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"message": str(exc), "code": "invalid_byok_credentials"},
    )


app.include_router(routes.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

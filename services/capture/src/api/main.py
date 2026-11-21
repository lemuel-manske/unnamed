from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from assembly import CaptureRuntime, CaptureSettings

HEALTH_CHECK_PATH = "/health"
HEALTH_CHECK_LIVENESS_PATH = f"{HEALTH_CHECK_PATH}/live"
HEALTH_CHECK_READINESS_PATH = f"{HEALTH_CHECK_PATH}/ready"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime = CaptureRuntime(CaptureSettings.from_environment())
    await runtime.start()
    app.state.runtime = runtime

    try:
        yield
    finally:
        await runtime.stop()


app = FastAPI(title="Castellani Capture", lifespan=lifespan)


@app.get(HEALTH_CHECK_LIVENESS_PATH)
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get(HEALTH_CHECK_READINESS_PATH)
async def ready(request: Request) -> dict[str, str]:
    runtime: CaptureRuntime | None = getattr(request.app.state, "runtime", None)

    if runtime is None or not runtime.ready:
        raise HTTPException(status_code=503, detail="Capture runtime is not ready")

    return {"status": "ok"}

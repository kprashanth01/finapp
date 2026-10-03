import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import JSONResponse

from app.auth_api import router as auth_router
from app.api import router
from app.goal_api import router as goal_router
from app.financial_details_api import router as financial_details_router
from app.loan_readiness_api import router as loan_readiness_router
from app.rl.api import router as research_router


class HealthResponse(BaseModel):
    status: str
    service: str


app = FastAPI(title="FinApp API")

LOCAL_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173",
                 "http://localhost:5174", "http://127.0.0.1:5174")
ALLOWED_ORIGINS = tuple(origin.strip().rstrip("/") for origin in
                        os.getenv("FINAPP_ALLOWED_ORIGINS", ",".join(LOCAL_ORIGINS)).split(",") if origin.strip())


@app.middleware("http")
async def protect_mutations_and_private_cache(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if request.headers.get("x-finapp-request") != "1" or (origin and origin not in ALLOWED_ORIGINS):
            return JSONResponse({"detail": "Request origin could not be verified."}, status_code=403,
                                headers={"Cache-Control": "no-store"})
        if request.headers.get("content-length", "0") != "0" and not request.headers.get("content-type", "").startswith("application/json"):
            return JSONResponse({"detail": "Use a JSON request body."}, status_code=415,
                                headers={"Cache-Control": "no-store"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


# The browser runs Vite on a different local origin during development.
# CORS is outermost, so rejected browser requests still receive CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-FinApp-Request"],
)

app.include_router(auth_router)
app.include_router(router)
app.include_router(goal_router)
app.include_router(financial_details_router)
app.include_router(loan_readiness_router)
app.include_router(research_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="finapp-api")

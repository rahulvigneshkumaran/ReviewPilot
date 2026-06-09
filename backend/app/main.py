from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

from app.api.router import api_router
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Automatically create tables on startup if they don't exist (ensures SQLite runs smoothly)
    from app.db.base import Base
    from app.core.database import engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed guidelines in DB and Qdrant on startup
    from app.core.database import async_session_factory
    from app.services.rag import rag_service
    async with async_session_factory() as db:
        await rag_service.seed_guidelines(db)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Register API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", response_class=HTMLResponse, tags=["System"])
async def root_dashboard():
    """Serves the interactive ReviewPilot dashboard console on localhost."""
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "resources", "dashboard.html")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>ReviewPilot API Running</h1><p>Visit <a href='/docs'>Swagger API docs</a></p>"

@app.get("/health", status_code=status.HTTP_200_OK, tags=["System"])
async def health_check():
    """Health check endpoint to verify backend service status."""
    return {"status": "healthy", "project": settings.PROJECT_NAME}

# Custom error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the details (normally would use logger.exception)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred.", "error": str(exc)},
    )

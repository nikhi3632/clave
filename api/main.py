from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import drill_down_router, query_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    print(f"Starting API server (debug={settings.debug})")
    print(f"CORS origins: {settings.cors_origin_list}")
    yield
    # Shutdown
    print("Shutting down API server")


app = FastAPI(
    title="Restaurant Analytics API",
    description="Natural language analytics for restaurant data",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(query_router)
app.include_router(drill_down_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Restaurant Analytics API",
        "version": "0.1.0",
        "status": "ok",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )

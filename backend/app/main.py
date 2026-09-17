from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .core.config import (
    PROJECT_NAME, API_V1_STR, BACKEND_CORS_ORIGINS,
    UPLOAD_DIR, PROCESSED_DIR
)
from .api.endpoints import router

# Create FastAPI app
app = FastAPI(
    title=PROJECT_NAME,
    description="PDF Scan Quality Checker - Analyze PDF quality and detect issues",
    version="1.0.0",
    openapi_url=f"{API_V1_STR}/openapi.json"
)

# Set up CORS
if BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API router
app.include_router(router, prefix=API_V1_STR)

# Mount static files for serving images and thumbnails
app.mount(f"{API_V1_STR}/static", StaticFiles(directory=str(UPLOAD_DIR)), name="static")

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "PDF Scan Quality Checker API",
        "version": "1.0.0",
        "docs": "/docs",
        "api": API_V1_STR
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": PROJECT_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

"""
ChimeraFlow API - FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ChimeraFlow API",
    description="Correlation engine for Excel, Access, and WhatsApp data sources",
    version="0.1.0"
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "chimeraflow-api",
        "version": "0.1.0"
    }


@app.get("/api/v1/sources")
async def list_sources():
    """List available data sources"""
    # TODO: Implement actual source detection in P1
    return {
        "sources": [],
        "message": "Connectors will be implemented in P1"
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "ChimeraFlow API",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

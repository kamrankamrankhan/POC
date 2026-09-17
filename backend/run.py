#!/usr/bin/env python3
"""
PDF Scan Quality Checker - Backend Server
Run this script to start the FastAPI server
"""

import uvicorn
from app.main import app

if __name__ == "__main__":
    print("🚀 Starting PDF Scan Quality Checker Backend...")
    print("📊 API Documentation: http://localhost:8000/docs")
    print("🔗 API Base URL: http://localhost:8000/api/v1")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 50)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )

#!/bin/bash

# PDF Scan Quality Checker - Startup Script
# This script starts both the backend and frontend services

echo "🚀 Starting PDF Scan Quality Checker POC System..."
echo "=================================================="

# Check if poppler-utils is installed
if ! command -v pdftoppm &> /dev/null; then
    echo "❌ Error: poppler-utils is not installed!"
    echo "Please install it using:"
    echo "  Ubuntu/Debian: sudo apt-get install poppler-utils"
    echo "  macOS: brew install poppler"
    echo "  Windows: Download from https://github.com/oschwartz10612/poppler-windows"
    exit 1
fi

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start backend
echo "🔧 Starting backend server..."
cd backend
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1

echo "🚀 Backend starting on http://localhost:8000"
python run.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend
echo "🎨 Starting frontend server..."
cd ../frontend
npm install > /dev/null 2>&1

echo "🚀 Frontend starting on http://localhost:3000"
npm start &
FRONTEND_PID=$!

echo ""
echo "✅ Both services are starting up!"
echo "📊 Backend API: http://localhost:8000"
echo "📊 API Docs: http://localhost:8000/docs"
echo "🎨 Frontend: http://localhost:3000"
echo ""
echo "⏹️  Press Ctrl+C to stop both services"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID

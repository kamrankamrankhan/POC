#!/bin/bash

# PDF Scan Quality Checker - Development Setup Script
# This script helps set up the development environment

echo "🔧 PDF Scan Quality Checker - Development Setup"
echo "=============================================="

# Check if poppler-utils is installed
if ! command -v pdftoppm &> /dev/null; then
    echo "❌ poppler-utils is not installed!"
    echo "Installing poppler-utils..."
    sudo apt update && sudo apt install -y poppler-utils
fi

# Setup backend
echo "📦 Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

echo "✅ Backend setup complete!"

# Setup frontend
echo "📦 Setting up frontend..."
cd ../frontend
npm install

echo "✅ Frontend setup complete!"

echo ""
echo "🚀 Development environment ready!"
echo ""
echo "To start the system:"
echo "  Backend:  cd backend && source venv/bin/activate && python run.py"
echo "  Frontend: cd frontend && npm start"
echo ""
echo "Or use the start script: ./start.sh"
echo ""
echo "📊 Backend API: http://localhost:8000"
echo "📊 API Docs: http://localhost:8000/docs"
echo "🎨 Frontend: http://localhost:3000"


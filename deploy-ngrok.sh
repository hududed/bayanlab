#!/bin/bash
# Quick ngrok deployment for Saturday's open house
# Temporary public URL - perfect for one-day event

set -e

echo "🎪 BayanLab Claim Portal - ngrok Deployment (Saturday Only)"
echo "==========================================================="
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "📦 Installing ngrok..."
    brew install ngrok
fi

# Check if API is running
if ! lsof -ti:8000 > /dev/null 2>&1; then
    echo "❌ API not running on port 8000"
    echo "Starting API server..."

    # Start API in background
    DATABASE_URL="postgresql+asyncpg://bayan:bayan@localhost:5433/bayan_backbone" \
    DATABASE_URL_SYNC="postgresql://bayan:bayan@localhost:5433/bayan_backbone" \
    uv run uvicorn backend.services.api_service.main:app --host 0.0.0.0 --port 8000 &

    echo "⏳ Waiting for API to start..."
    sleep 5
fi

echo "✅ API running on http://localhost:8000"
echo ""
echo "🌐 Starting ngrok tunnel..."
echo ""

# Start ngrok
ngrok http 8000

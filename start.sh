#!/usr/bin/env bash
# ============================================================
# "Are You Okay?" — Startup Launcher
# ============================================================
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================================="
echo "💚 'Are You Okay?' (আর ইউ ওকে?) — AI Family Care Layer"
echo "=========================================================="

# Create virtual environment if missing
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    if command -v uv &> /dev/null; then
        uv venv --python 3.11 .venv
    else
        python3 -m venv .venv
    fi
fi

# Activate venv
source .venv/bin/activate

# Install dependencies if needed
echo "🔍 Checking python dependencies..."
if command -v uv &> /dev/null; then
    uv pip install --python .venv/bin/python -r requirements.txt
else
    pip install -r requirements.txt
fi

# Ensure alerts.json exists
if [ ! -f "alerts.json" ]; then
    echo "[]" > alerts.json
fi

# Ensure data directories exist
mkdir -p data/audio_cache

echo "🚀 Starting FastAPI server on http://localhost:8000 ..."
echo "👉 Open http://localhost:8000 in your browser to interact."
echo "Press Ctrl+C to terminate."
echo "----------------------------------------------------------"

exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

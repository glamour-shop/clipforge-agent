#!/usr/bin/env bash
set -e

echo "==================================================="
echo "            ClipForge Installation Script          "
echo "==================================================="

echo "[1/4] Checking Python 3.12..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 not found. Please install Python 3.12."
    exit 1
fi

echo "[2/4] Setting up Python virtual environment (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

echo "[3/4] Installing dependencies from requirements.txt..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[4/4] Checking environment configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from template."
fi

echo ""
echo "==================================================="
echo "[SUCCESS] ClipForge is ready!"
echo "To start the application, run:"
echo "  streamlit run app.py"
echo "==================================================="

#!/bin/bash
# Setup script for video downloader project

set -e

echo "🚀 Setting up Video Downloader project..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running from project root
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required tools
echo "📋 Checking prerequisites..."

# Check for Python
if ! command_exists python3; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    echo "   Install from: https://www.python.org/downloads/"
    exit 1
else
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓${NC} Found $PYTHON_VERSION"
fi

# Check for Node.js
if ! command_exists node; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    echo "   Install from: https://nodejs.org/"
    exit 1
else
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Found Node.js $NODE_VERSION"
fi

# Check for pnpm
if ! command_exists pnpm; then
    echo -e "${YELLOW}⚠${NC}  pnpm is not installed"
    echo "   Installing pnpm globally..."
    npm install -g pnpm
    echo -e "${GREEN}✓${NC} pnpm installed"
else
    PNPM_VERSION=$(pnpm --version)
    echo -e "${GREEN}✓${NC} Found pnpm $PNPM_VERSION"
fi

# Check for uv (Python dependency manager)
if ! command_exists uv; then
    echo -e "${YELLOW}⚠${NC}  uv is not installed"
    echo "   Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo -e "${GREEN}✓${NC} uv installed"
else
    UV_VERSION=$(uv --version)
    echo -e "${GREEN}✓${NC} Found $UV_VERSION"
fi

# Check for yt-dlp
if ! command_exists yt-dlp; then
    echo -e "${YELLOW}⚠${NC}  yt-dlp is not installed system-wide"
    echo "   Note: yt-dlp will be installed as a Python dependency (recommended)"
    echo "   Alternatively, you can install it system-wide:"
    echo "   - macOS: brew install yt-dlp"
    echo "   - Linux: sudo apt install yt-dlp"
    echo ""
else
    YTDLP_VERSION=$(yt-dlp --version)
    echo -e "${GREEN}✓${NC} Found yt-dlp $YTDLP_VERSION"
fi

echo ""
echo "📦 Installing dependencies..."
echo ""

# Setup Backend
echo "🐍 Setting up Backend..."
cd backend

# Copy .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "   Copying .env.example to .env"
    cp .env.example .env
fi

# Install Python dependencies
echo "   Installing Python dependencies..."
uv sync --quiet

echo -e "${GREEN}✓${NC} Backend setup complete"
cd ..

# Setup Frontend
echo ""
echo "⚛️  Setting up Frontend..."
cd frontend

# Copy .env.local if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo "   Copying .env.example to .env.local"
    cp .env.example .env.local
fi

# Install Node dependencies
echo "   Installing Node dependencies (this may take a minute)..."
pnpm install --silent

echo -e "${GREEN}✓${NC} Frontend setup complete"
cd ..

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "📚 Next steps:"
echo ""
echo "  Option 1 - Docker Compose (easiest):"
echo "    docker-compose up"
echo ""
echo "  Option 2 - Manual:"
echo "    Terminal 1: cd backend && uv run uvicorn app.main:app --reload"
echo "    Terminal 2: cd frontend && pnpm dev"
echo ""
echo "  Then visit: http://localhost:3000"
echo ""
echo "📖 For more info, see:"
echo "   - QUICKSTART.md"
echo "   - README.md"
echo ""

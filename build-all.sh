#!/bin/bash
###############################################################################
# GPSS Agent - Multi-Platform Build Script
# Builds executables for Linux, Windows (via Wine), and macOS
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "GPSS Agent - Multi-Platform Builder"
echo "============================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 3 found: $(python3 --version)"

# Check PyInstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC}  PyInstaller not found. Installing..."
    pip3 install pyinstaller
fi

echo -e "${GREEN}✓${NC} PyInstaller found"
echo ""

# Create dist directory
mkdir -p dist
mkdir -p build

# Detect platform
PLATFORM=$(uname -s)
echo "Detected platform: $PLATFORM"
echo ""

###############################################################################
# Build for current platform
###############################################################################

case "$PLATFORM" in
    Linux)
        echo "============================================================"
        echo "Building for Linux (current platform)"
        echo "============================================================"

        pyinstaller --clean gpss-agent.spec

        if [ -f "dist/GPSS-Agent" ]; then
            chmod +x dist/GPSS-Agent
            SIZE=$(du -h dist/GPSS-Agent | cut -f1)
            echo -e "${GREEN}✓${NC} Linux executable built: dist/GPSS-Agent ($SIZE)"

            # Create versioned copy
            cp dist/GPSS-Agent "dist/gpss-agent-linux-$(uname -m)"
            echo -e "${GREEN}✓${NC} Created: dist/gpss-agent-linux-$(uname -m)"
        else
            echo -e "${RED}✗${NC} Build failed"
            exit 1
        fi
        ;;

    Darwin)
        echo "============================================================"
        echo "Building for macOS (current platform)"
        echo "============================================================"

        pyinstaller --clean gpss-agent.spec

        if [ -f "dist/GPSS-Agent" ]; then
            chmod +x dist/GPSS-Agent
            SIZE=$(du -h dist/GPSS-Agent | cut -f1)
            echo -e "${GREEN}✓${NC} macOS executable built: dist/GPSS-Agent ($SIZE)"

            # Create versioned copy
            cp dist/GPSS-Agent "dist/GPSS-Agent-macOS-$(uname -m)"
            echo -e "${GREEN}✓${NC} Created: dist/GPSS-Agent-macOS-$(uname -m)"
        else
            echo -e "${RED}✗${NC} Build failed"
            exit 1
        fi
        ;;

    MINGW*|MSYS*|CYGWIN*)
        echo "============================================================"
        echo "Building for Windows (current platform)"
        echo "============================================================"

        pyinstaller --clean gpss-agent.spec

        if [ -f "dist/GPSS-Agent.exe" ]; then
            SIZE=$(du -h dist/GPSS-Agent.exe | cut -f1)
            echo -e "${GREEN}✓${NC} Windows executable built: dist/GPSS-Agent.exe ($SIZE)"

            # Create versioned copy
            cp dist/GPSS-Agent.exe "dist/GPSS-Agent-Windows-x64.exe"
            echo -e "${GREEN}✓${NC} Created: dist/GPSS-Agent-Windows-x64.exe"
        else
            echo -e "${RED}✗${NC} Build failed"
            exit 1
        fi
        ;;

    *)
        echo -e "${RED}✗${NC} Unsupported platform: $PLATFORM"
        exit 1
        ;;
esac

echo ""
echo "============================================================"
echo "Build Summary"
echo "============================================================"
ls -lh dist/GPSS-Agent* 2>/dev/null || ls -lh dist/gpss-agent* 2>/dev/null
echo ""
echo -e "${GREEN}✓${NC} Build completed successfully!"
echo ""
echo "To deploy to server:"
echo "  scp dist/GPSS-Agent* root@vm.gpss.ro:/var/www/vm.gpss.ro/installers/"
echo ""

#!/bin/bash
# One-line install command for TeleCursor (macOS/Linux) - With Python Detection
# Usage: curl -fsSL https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.sh | bash

set -e

# ======== FUNCTION: Check for Python ========
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON="python3"
    elif command -v python &> /dev/null; then
        PYTHON="python"
    else
        echo "❌ Python 3 not found."
        echo ""
        echo "Please install Python 3.10+ manually:"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "   brew install python"
        elif command -v apt-get &> /dev/null; then
            echo "   sudo apt-get install python3 python3-pip python3-venv"
        elif command -v dnf &> /dev/null; then
            echo "   sudo dnf install python3 python3-pip"
        elif command -v yum &> /dev/null; then
            echo "   sudo yum install python3 python3-pip"
        elif command -v pacman &> /dev/null; then
            echo "   sudo pacman -S python python-pip"
        else
            echo "   Please install Python 3.10+ manually from https://python.org"
        fi
        echo ""
        echo "After installing Python, run this script again."
        exit 1
    fi
    echo "✅ Using $PYTHON — $("$PYTHON" --version)"
    echo ""
}

# ======== MAIN: Check OS ========
OS="$(uname -s)"
case "$OS" in
  Darwin*)
    PLATFORM="macOS"
    ;;
  Linux*)
    PLATFORM="Linux"
    ;;
  CYGWIN*|MINGW*|MSYS*)
    echo "🪟 Windows detected!"
    echo ""
    echo "This script is for macOS/Linux only."
    echo "Please run the PowerShell installer instead:"
    echo ""
    echo "   irm https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.ps1 | iex"
    echo ""
    echo "Or open PowerShell and run:"
    echo "   Invoke-RestMethod https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.ps1 | Invoke-Expression"
    exit 1
    ;;
  *)
    echo "⚠️  Unrecognized OS: $OS"
    echo "   Please follow manual installation steps in README.md"
    exit 1
    ;;
esac

echo "🚀 Installing TeleCursor on $PLATFORM..."

# Check for Python
check_python

# Check if git is available
if ! command -v git &> /dev/null; then
    echo "❌ Error: git is required but not installed. Please install git first."
    exit 1
fi

# Clone the repository
echo "📥 Cloning TeleCursor repository..."
git clone https://github.com/noobsmoker/telecursor.git

# Setup instructions
echo ""
echo "✅ Repository cloned successfully!"
echo ""
echo "📋 Next steps:"
echo "1. cd telecursor"
echo "2. Follow the setup instructions in README.md"
echo ""
echo "🔧 For development:"
echo "   • Server: cd server && npm install && npm run dev"
echo "   • Extension: Load browser-extension/ in Chrome/Firefox (developer mode)"
echo "   • Models: cd models/stage1_cursor_dynamics && pip install -r requirements.txt"
echo ""
echo "📚 Documentation: https://github.com/noobsmoker/telecursor#readme"
echo ""
echo "🎉 Installation complete!"
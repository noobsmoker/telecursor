#!/bin/bash
# One-line install command for TeleCursor (macOS/Linux)
# Usage: curl -fsSL https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.sh | bash

set -e

# Check OS and provide appropriate instructions
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
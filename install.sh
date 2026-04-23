#!/bin/bash
# One-line install command for TeleCursor
# Usage: curl -fsSL https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.sh | bash

set -e

echo "🚀 Installing TeleCursor..."

# Check if git is available
if ! command -v git &> /dev/null; then
    echo "❌ Error: git is required but not installed. Please install git first."
    exit 1
fi

# Clone the repository
echo "📥 Cloning TeleCursor repository..."
git clone https://github.com/noobsmoker/telecursor.git
cd telecursor

# Check OS and provide appropriate instructions
OS="$(uname -s)"
case "$OS" in
  Darwin*)
    echo "🍎 Detected macOS"
    ;;
  Linux*)
    echo "🐧 Detected Linux"
    ;;
  CYGWIN*|MINGW*|MSYS*)
    echo "🪟 Detected Windows"
    ;;
  *)
    echo "⚠️  Unrecognized OS: $OS. Please follow manual installation steps."
    echo "    This script works best in Git Bash, WSL, or macOS/Linux terminals."
    ;;
esac

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
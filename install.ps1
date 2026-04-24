# TeleCursor Windows Install Script (PowerShell)
# Usage: irm https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host "Installing TeleCursor on Windows..." -ForegroundColor Cyan

# Check prerequisites
$node = Get-Command node -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue

if (-not $node) {
    Write-Host "❌ Error: Node.js 20+ is required but not installed." -ForegroundColor Red
    Write-Host "   Please install from https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

if (-not $python) {
    Write-Host "❌ Error: Python 3.10+ is required but not installed." -ForegroundColor Red
    Write-Host "   Please install from https://python.org/" -ForegroundColor Yellow
    exit 1
}

# Check Node.js version
$nodeVersion = (node --version).Substring(1)
$nodeMajor = [int]($nodeVersion.Split('.')[0])
if ($nodeMajor -lt 20) {
    Write-Host "❌ Error: Node.js 20+ required. Found: v$nodeVersion" -ForegroundColor Red
    exit 1
}

# Check Python version
$pythonVersion = (python --version).Split(' ')[1]
$pythonMajor = [int]($pythonVersion.Split('.')[0])
$pythonMinor = [int]($pythonVersion.Split('.')[1])
if ($pythonMajor -lt 3 -or ($pythonMajor -eq 3 -and $pythonMinor -lt 10)) {
    Write-Host "❌ Error: Python 3.10+ required. Found: $pythonVersion" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Prerequisites check passed" -ForegroundColor Green

# Clone or use existing repo
$repoUrl = "https://github.com/noobsmoker/telecursor.git"
$installDir = "$env:USERPROFILE\telecursor"

if (Test-Path $installDir) {
    Write-Host "📁 Directory exists, pulling latest changes..." -ForegroundColor Yellow
    Set-Location $installDir
    git pull
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  Git pull failed, but continuing..." -ForegroundColor Yellow
    }
} else {
    Write-Host "📥 Cloning repository..." -ForegroundColor Green
    git clone $repoUrl $installDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to clone repository" -ForegroundColor Red
        exit 1
    }
    Set-Location $installDir
}

# Install server dependencies
Write-Host "📦 Installing server dependencies..." -ForegroundColor Green
Set-Location "$installDir\server"
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install Node.js dependencies" -ForegroundColor Red
    exit 1
}

# Install Python model dependencies
Write-Host "🐍 Installing Python dependencies..." -ForegroundColor Green
Set-Location "$installDir\models\stage1_cursor_dynamics"
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install Python dependencies" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "⚠️  requirements.txt not found, skipping Python dependencies" -ForegroundColor Yellow
}

# Return to install directory
Set-Location $installDir

Write-Host ""
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🎉 TeleCursor has been installed to: $installDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "📋 Next steps:" -ForegroundColor Yellow
Write-Host "   1. Start the server:" -ForegroundColor White
Write-Host "      cd $installDir\server" -ForegroundColor Gray
Write-Host "      npm run dev" -ForegroundColor Gray
Write-Host ""
Write-Host "   2. Load the browser extension:" -ForegroundColor White
Write-Host "      - Open Chrome -> Extensions -> Enable Developer mode" -ForegroundColor Gray
Write-Host "      - Click 'Load unpacked' -> Select: $installDir\browser-extension" -ForegroundColor Gray
Write-Host ""
Write-Host "   3. For model training (optional):" -ForegroundColor White
Write-Host "      cd $installDir\models\stage1_cursor_dynamics" -ForegroundColor Gray
Write-Host "      python train.py --data-dir /path/to/trajectories --config config.yaml" -ForegroundColor Gray
Write-Host ""
Write-Host "📚 Documentation: https://github.com/noobsmoker/telecursor#readme" -ForegroundColor Cyan
Write-Host "🐛 Issues: https://github.com/noobsmoker/telecursor/issues" -ForegroundColor Cyan

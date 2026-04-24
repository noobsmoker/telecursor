# TeleCursor Windows Install Script (PowerShell)
# Usage: irm https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host "Installing TeleCursor on Windows..." -ForegroundColor Cyan

# ======== FUNCTION: Test for Python installation ========
function Test-Python {
    $pythonCmds = @("python", "python3", "py")
    foreach ($cmd in $pythonCmds) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            return $cmd
        }
    }
    return $null
}

# ======== FUNCTION: Install Python silently via winget ========
function Install-Python {
    Write-Host "🐍 Python not found. Attempting to install via winget..." -ForegroundColor Yellow
    winget install --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python installation via winget failed. Install manually: https://python.org"
        exit 1
    }
    # Refresh PATH in current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# ======== FUNCTION: Install Git via winget ========
function Install-Git {
    if (Get-CommandSafe "git") {
        return  # Already installed
    }
    Write-Host "🔧 Git not found. Installing Git via winget..." -ForegroundColor Yellow
    winget install --id Git.Git --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Git installation via winget failed. Please install Git manually."
        exit 1
    }
    # Refresh PATH with Git's location
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# Small helper
function Get-CommandSafe {
    param([string]$Name)
    Get-Command $Name -ErrorAction SilentlyContinue
}

# ======== FUNCTION: Handle Python App Execution Alias Bug ========
function Handle-AppAlias {
    try {
        $ver = & python --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            return $true  # Alias present but broken
        }
    } catch {
        return $true
    }
    return $false
}

# ======== MAIN: Dependency Checks ========

# 1) Python
$python = Test-Python
$haveValidPython = $false

if ($python) {
    # Check if it's the fake Windows Store alias
    if (Handle-AppAlias) {
        Write-Warning "Python App Execution Alias detected but Python not actually installed."
        Install-Python
    } else {
        $haveValidPython = $true
    }
} else {
    Install-Python
}

# Re-check after possible install
if (-not $haveValidPython) {
    $python = Test-Python
    if (-not $python) {
        Write-Error "Python installation failed or not found in PATH. Please restart terminal and try again."
        exit 1
    }
}

Write-Host "🐍 Using Python: $(Invoke-Expression "$python --version")" -ForegroundColor Green

# 2) Git
Install-Git
Write-Host "🔧 Git is available." -ForegroundColor Green

# ======== REST OF INSTALLATION ========

Write-Host ""
Write-Host "✅ Prerequisites satisfied. Continuing with TeleCursor setup..." -ForegroundColor Green

# Check if git is installed
if (-not (Get-CommandSafe "git")) {
    Write-Error "git is still not available after installation."
    exit 1
}

# Clone the repository
$installDir = "$env:USERPROFILE\telecursor"
if (Test-Path $installDir) {
    Write-Host "📁 Directory exists, pulling latest..." -ForegroundColor Yellow
    Set-Location $installDir
    git pull
} else {
    Write-Host "📥 Cloning repository..." -ForegroundColor Green
    git clone https://github.com/noobsmoker/telecursor.git $installDir
    Set-Location $installDir
}

# Install server dependencies
Write-Host "📦 Installing server dependencies..." -ForegroundColor Green
Set-Location "$installDir\server"
npm install

# Install Python model dependencies
Write-Host "🐍 Installing Python dependencies..." -ForegroundColor Green
Set-Location "$installDir\models\stage1_cursor_dynamics"
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
}

# Done
Set-Location $installDir
Write-Host ""
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host "📍 Installed to: $installDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "🚀 To start the server:" -ForegroundColor Yellow
Write-Host "   cd $installDir\server" -ForegroundColor White
Write-Host "   npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "🖥️  To load extension: Chrome -> Extensions -> Developer mode" -ForegroundColor Yellow
Write-Host "   -> Load unpacked -> Select: $installDir\browser-extension" -ForegroundColor White
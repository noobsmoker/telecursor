# TeleCursor Windows Install Script (PowerShell)
# Usage: irm https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host "Installing TeleCursor on Windows..." -ForegroundColor Cyan

# ======== FUNCTION: Test for Python installation ========
function Test-Python {
    $pythonCmds = @("python", "python3", "py")
    foreach ($cmd in $pythonCmds) {
        $pythonCmd = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($pythonCmd) {
            return $cmd
        }
    }
    return $null
}

# ======== FUNCTION: Install Python via winget ========
function Install-Python {
    Write-Host "Python not found. Installing Python 3.11 via winget..." -ForegroundColor Yellow
    
    # Correct winget syntax - use the query directly or --id flag
    winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Trying alternative installation method..." -ForegroundColor Yellow
        # Try without --id flag, just use the package ID as query
        winget install Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python installation via winget failed. Please install Python 3.10+ manually from https://python.org"
        exit 1
    }
    
    # Refresh PATH in current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Write-Host "Python installed successfully." -ForegroundColor Green
}

# ======== FUNCTION: Install Git via winget ========
function Install-Git {
    if (Get-Command "git" -ErrorAction SilentlyContinue) {
        return  # Already installed
    }
    
    Write-Host "Git not found. Installing Git via winget..." -ForegroundColor Yellow
    
    # Correct winget syntax for Git
    winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Trying alternative installation method..." -ForegroundColor Yellow
        winget install Git.Git -e --silent --accept-package-agreements --accept-source-agreements
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Git installation via winget failed. Please install Git manually from https://git-scm.com/"
        exit 1
    }
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Write-Host "Git installed successfully." -ForegroundColor Green
}

# ======== FUNCTION: Handle Python App Execution Alias Bug ========
function Handle-AppAlias {
    try {
        $result = & python --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            return $true  # Alias present but broken
        }
    } catch {
        return $true
    }
    return $false
}

# ======== MAIN: Dependency Checks ========

Write-Host "Checking dependencies..." -ForegroundColor Green

# 1) Check Python
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

Write-Host "Using Python: $(& $python --version)" -ForegroundColor Green

# 2) Check Git
Install-Git
Write-Host "Git is available." -ForegroundColor Green

# ======== CLONE AND INSTALL TELECURSOR ========

Write-Host ""
Write-Host "Prerequisites satisfied. Setting up TeleCursor..." -ForegroundColor Green

# Clone the repository
$installDir = "$env:USERPROFILE\telecursor"

if (Test-Path $installDir) {
    Write-Host "Directory exists, pulling latest changes..." -ForegroundColor Yellow
    Set-Location $installDir
    git pull origin main
} else {
    Write-Host "Cloning TeleCursor repository..." -ForegroundColor Green
    git clone https://github.com/noobsmoker/telecursor.git $installDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to clone repository"
        exit 1
    }
    Set-Location $installDir
}

# Install server dependencies (Node.js)
Write-Host "Installing Node.js dependencies..." -ForegroundColor Green
Set-Location "$installDir\server"
if (Test-Path "package.json") {
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install Node.js dependencies"
        exit 1
    }
} else {
    Write-Warning "package.json not found in server directory"
}

# Install Python model dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Green
Set-Location "$installDir\models\stage1_cursor_dynamics"
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to install some Python dependencies"
    }
} else {
    Write-Warning "requirements.txt not found"
}

# Done
Set-Location $installDir
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TeleCursor Installation Complete!" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Installed to: $installDir" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Start the server:" -ForegroundColor White
Write-Host "     cd $installDir\server" -ForegroundColor Gray
Write-Host "     npm run dev" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Load the browser extension:" -ForegroundColor White
Write-Host "     Open Chrome -> Extensions -> Enable Developer mode" -ForegroundColor Gray
Write-Host "     Click 'Load unpacked' -> Select: $installDir\browser-extension" -ForegroundColor Gray
Write-Host ""
Write-Host "Documentation: https://github.com/noobsmoker/telecursor" -ForegroundColor Cyan

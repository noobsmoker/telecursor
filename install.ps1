# TeleCursor Windows Install Script (PowerShell) - With Python Detection & Silent Install
# Usage: irm https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host "Installing TeleCursor on Windows..." -ForegroundColor Cyan

# ======== FUNCTION: Test for Python installation ========
function Test-Python {
    $pythonCmd = $null
    foreach ($cmd in @("python", "python3", "py")) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            $pythonCmd = $cmd
            break
        }
    }
    return $pythonCmd
}

# ======== FUNCTION: Install Python silently via winget ========
function Install-Python {
    Write-Host "🐍 Python not found. Attempting to install via winget..." -ForegroundColor Yellow
    winget install --name "Python" --package-name "Python.Python.3.11" --accept-package-agreements --accept-source-agreements --silent --no-silent-mode
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python installation via winget failed. Please install Python 3.10+ manually from https://python.org"
        exit 1
    }
    # Refresh PATH in current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    # Add Git installation
    Install-Git
}

function Install-Git {
    if (Get-CommandSafe "git") {
        return  # Already installed
    }
    Write-Host "🔧 Git not found. Installing Git via winget..." -ForegroundColor Yellow
    winget install --name "Git" --package-name "Git.Git" --accept-package-agreements --accept-source-agreements --silent --no-silent-mode
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Git installation via winget failed. Please install Git manually."
        exit 1
    }
    # Refresh PATH with Git's location
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}
        # Refresh PATH in current session
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        Write-Error "winget not available. Please install Python 3.10+ manually from https://python.org"
        exit 1
    }
}

# ======== FUNCTION: Handle App Execution Alias Bug ========
function Handle-AppAlias {
    $pythonVersion = Invoke-Expression "python --version 2>&1"
    if ($pythonVersion -match "not found" -or $LASTEXITCODE -ne 0) {
        Write-Warning "Python App Execution Alias detected but Python is not actually installed."
        Write-Host "Attempting to install Python via winget..." -ForegroundColor Green
        Install-Python
        $pythonVersion = Invoke-Expression "python --version 2>&1"
        if ($pythonVersion -match "not found" -or $LASTEXITCODE -ne 0) {
            Write-Error "Python installation failed or not found in PATH. Please restart your terminal and try again."
            exit 1
        }
    }
}

# ======== MAIN: Check for Python ========
$python = Test-Python
if (-not $python) {
    Install-Python
    $python = Test-Python
    if (-not $python) {
        Write-Error "Python installation failed or not found in PATH. Please restart your terminal and try again."
        exit 1
    }
}

Write-Host "Using Python: $(Invoke-Expression "$python --version")" -ForegroundColor Green

# ======== Rest of Installation (simplified placeholder) ========
# Original install logic continues here...
# This script would normally clone repo, install dependencies, etc.
# For brevity, we just indicate next steps:

Write-Host ""
Write-Host "🚀 TeleCursor installation preparatory steps completed!" -ForegroundColor Green
Write-Host "Next steps will clone the repo and install Node.js dependencies..." -ForegroundColor Yellow

# Twitter Shilling Bot Setup Script for Windows PowerShell
# Run this script if the .bat file doesn't work

Write-Host "Twitter Shilling Bot Setup" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green

# Check if Python is installed
try {
    $pythonVersion = python --version 2>$null
    Write-Host "Found Python: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "Error: Python not found. Please install Python 3.8+ first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
try {
    python -m venv venv
    Write-Host "Virtual environment created successfully!" -ForegroundColor Green
}
catch {
    Write-Host "Error: Failed to create virtual environment." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
try {
    & ".\venv\Scripts\Activate.ps1"
    Write-Host "Virtual environment activated!" -ForegroundColor Green
}
catch {
    Write-Host "Warning: Could not activate with PowerShell. Trying alternative..." -ForegroundColor Yellow
    try {
        cmd /c "venv\Scripts\activate.bat"
        Write-Host "Virtual environment activated with cmd!" -ForegroundColor Green
    }
    catch {
        Write-Host "Error: Failed to activate virtual environment." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install packages
Write-Host "Installing required packages..." -ForegroundColor Yellow
$packages = @(
    "python-telegram-bot",
    "tweepy", 
    "groq",
    "python-dotenv",
    "aiohttp",
    "requests",
    "loguru",
    "schedule",
    "tenacity"
)

foreach ($package in $packages) {
    Write-Host "Installing $package..." -ForegroundColor Cyan
    try {
        pip install $package
        Write-Host "✓ $package installed successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "✗ Failed to install $package" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "===============" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Copy .env.example to .env and fill in your credentials"
Write-Host "2. To run the bot:"
Write-Host "   - Activate environment: .\venv\Scripts\Activate.ps1"
Write-Host "   - Start bot: python main.py"
Write-Host ""

Read-Host "Press Enter to continue"
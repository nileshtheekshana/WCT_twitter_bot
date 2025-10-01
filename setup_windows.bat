@echo off
echo Creating virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo Error: Failed to create virtual environment. Make sure Python is installed.
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate
if %errorlevel% neq 0 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing requirements...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error: Failed to install requirements. Trying individual packages...
    echo Installing core packages...
    pip install python-telegram-bot tweepy groq python-dotenv aiohttp requests loguru schedule tenacity
)

echo Setup complete!
echo.
echo To start the bot:
echo 1. Copy .env.example to .env and fill in your credentials
echo 2. Run: venv\Scripts\activate
echo 3. Run: python main.py

pause
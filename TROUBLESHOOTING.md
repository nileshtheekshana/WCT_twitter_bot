# Twitter Shilling Bot - Troubleshooting Guide

## Common Setup Issues & Solutions

### 1. Groq AI Model Decommissioned Error

**Problem**: "The model `llama3-8b-8192` has been decommissioned"

**Solution**: The bot now uses updated models automatically. Supported models:
- `llama-3.1-8b-instant` (default)
- `llama-3.3-70b-versatile` (fallback)
- `openai/gpt-oss-20b` (fallback)

To change the model, set in your `.env` file:
```
AI_MODEL=llama-3.1-8b-instant
```

Test the AI validator:
```bash
python test_ai.py
```

### 2. pip install -r requirements.txt Error

**Problem**: Package installation fails with various errors.

**Solutions**:

#### Option A: Use the PowerShell Script
```powershell
# Run this in PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup_windows.ps1
```

#### Option B: Manual Installation
```bash
# Activate virtual environment first
.\venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install packages one by one
pip install python-telegram-bot
pip install tweepy
pip install groq
pip install python-dotenv
pip install aiohttp
pip install requests
pip install loguru
pip install schedule
pip install tenacity
```

#### Option C: Use Conda (if you have Anaconda/Miniconda)
```bash
conda create -n twitter_bot python=3.11
conda activate twitter_bot
pip install -r requirements.txt
```

### 2. PowerShell Execution Policy Error

**Problem**: "execution of scripts is disabled on this system"

**Solution**:
```powershell
# Run PowerShell as Administrator and execute:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then try the setup again
.\setup_windows.ps1
```

### 3. Python Not Found Error

**Problem**: "python is not recognized as an internal or external command"

**Solutions**:
1. **Install Python**: Download from https://python.org (version 3.8+)
2. **Add to PATH**: During installation, check "Add Python to PATH"
3. **Manual PATH**: Add Python installation directory to system PATH

### 4. Virtual Environment Issues

**Problem**: Cannot create or activate virtual environment

**Solutions**:

#### Windows Command Prompt:
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

#### Windows PowerShell:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### If activation fails:
```cmd
# Use cmd instead of PowerShell
cmd /c "venv\Scripts\activate.bat && pip install -r requirements.txt"
```

### 5. Package Compatibility Issues

**Problem**: Specific packages fail to install

**Solutions**:

#### For python-telegram-bot:
```bash
pip install python-telegram-bot[all]
# or
pip install python-telegram-bot==20.0
```

#### For tweepy:
```bash
pip install tweepy==4.14.0
```

#### For groq:
```bash
pip install groq --upgrade
```

### 6. SSL Certificate Errors

**Problem**: SSL verification failed during pip install

**Solutions**:
```bash
# Temporary fix (not recommended for production)
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

# Better solution: Update certificates
pip install --upgrade certifi
```

### 7. Permission Errors

**Problem**: Access denied or permission errors

**Solutions**:
1. **Run as Administrator**: Right-click CMD/PowerShell → "Run as administrator"
2. **User installation**: Use `pip install --user package_name`
3. **Virtual environment**: Always use virtual environment (recommended)

### 8. Import Errors After Installation

**Problem**: "ModuleNotFoundError" even after installation

**Solutions**:

#### Check virtual environment:
```bash
# Make sure you're in the virtual environment
.\venv\Scripts\activate

# Verify installations
pip list

# Test imports
python test_setup.py
```

#### Reinstall problematic packages:
```bash
pip uninstall package_name
pip install package_name
```

### 9. Version Conflicts

**Problem**: Package version conflicts

**Solutions**:

#### Create fresh environment:
```bash
# Remove old environment
rmdir /s venv

# Create new one
python -m venv venv
.\venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Use specific versions:
```bash
pip install python-telegram-bot==20.0
pip install tweepy==4.14.0
```

### 10. Windows Long Path Issues

**Problem**: Path too long errors

**Solutions**:
1. **Move to shorter path**: Like `C:\twitter_bot\`
2. **Enable long paths**: 
   - Run `gpedit.msc` as admin
   - Navigate to: Computer Configuration → Administrative Templates → System → Filesystem
   - Enable "Enable Win32 long paths"

## Testing Your Setup

After installation, run these tests:

```bash
# Activate environment
.\venv\Scripts\activate

# Test dependencies
python test_setup.py

# Test Python version
python --version

# Test pip
pip --version

# List installed packages
pip list
```

## Alternative Installation Methods

### Method 1: Conda Environment
```bash
conda create -n twitter_bot python=3.11
conda activate twitter_bot
pip install -r requirements.txt
```

### Method 2: Docker (Advanced)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Method 3: System Python (Not Recommended)
```bash
# Install directly to system Python
pip install --user -r requirements.txt
```

## Getting Help

If you're still having issues:

1. **Check Python version**: Must be 3.8 or higher
2. **Try the test script**: `python test_setup.py`
3. **Check the logs**: Look in the `logs/` directory
4. **Use verbose pip**: `pip install -v package_name` for detailed output
5. **Clear pip cache**: `pip cache purge` then try again

## Environment Variables Setup

After successful installation:

1. Copy `.env.example` to `.env`
2. Fill in all required credentials:
   - Telegram bot token and chat IDs
   - Twitter API keys (5 accounts)
   - Groq AI API key

3. Test configuration:
```bash
python -c "from src.config import config; print('Config loaded successfully!')"
```

Remember: Never commit your `.env` file to git - it contains sensitive credentials!
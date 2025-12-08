#!/bin/bash

# Twitter Shilling Bot - VPS Deployment Script

echo "🤖 Twitter Shilling Bot - VPS Deployment"
echo "========================================"

# Update system
echo "📦 Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install Python 3 and pip
echo "🐍 Installing Python 3 and pip..."
sudo apt install -y python3 python3-pip python3-venv

# Install system dependencies
echo "📚 Installing system dependencies..."
sudo apt install -y git curl wget screen tmux

# Create bot directory
echo "📁 Setting up bot directory..."
BOT_DIR="/opt/twitter_shilling_bot"
sudo mkdir -p $BOT_DIR
sudo chown $USER:$USER $BOT_DIR

# Clone or copy files - user should do this manually first
echo "📋 Please ensure you have copied all bot files to $BOT_DIR"
echo "   Including: main.py, src/, requirements.txt, .env"
read -p "Press Enter when files are ready..."

cd $BOT_DIR

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found in $BOT_DIR"
    echo "Please copy all bot files first!"
    exit 1
fi

# Setup Python virtual environment
echo "🔧 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Install TgCrypto for faster Pyrogram (optional but recommended)
pip install tgcrypto

# Create logs directory
mkdir -p logs

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️ Warning: .env file not found!"
    echo "Please create .env with your API keys before starting the bot."
fi

# Set up systemd service
echo "⚙️ Setting up systemd service..."
sudo tee /etc/systemd/system/twitter-bot.service > /dev/null <<EOF
[Unit]
Description=Twitter Shilling Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BOT_DIR
Environment=PATH=$BOT_DIR/venv/bin
ExecStart=$BOT_DIR/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:$BOT_DIR/logs/bot.log
StandardError=append:$BOT_DIR/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo "✅ VPS setup complete!"
echo ""
echo "========================================"
echo "📋 Commands to manage the bot:"
echo "========================================"
echo ""
echo "Start bot:     sudo systemctl start twitter-bot"
echo "Stop bot:      sudo systemctl stop twitter-bot"
echo "Restart bot:   sudo systemctl restart twitter-bot"
echo "Check status:  sudo systemctl status twitter-bot"
echo "View logs:     tail -f $BOT_DIR/logs/bot.log"
echo "Enable auto-start: sudo systemctl enable twitter-bot"
echo ""
echo "Alternative (using screen):"
echo "  cd $BOT_DIR && source venv/bin/activate && screen -S bot python main.py"
echo ""
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
cd /opt
sudo mkdir -p twitter_shilling_bot
sudo chown $USER:$USER twitter_shilling_bot
cd twitter_shilling_bot

# Setup Python virtual environment
echo "🔧 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Create logs directory
mkdir -p logs

# Set up systemd service (optional)
echo "⚙️ Setting up systemd service..."
sudo tee /etc/systemd/system/twitter-bot.service > /dev/null <<EOF
[Unit]
Description=Twitter Shilling Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/twitter_shilling_bot
Environment=PATH=/opt/twitter_shilling_bot/venv/bin
ExecStart=/opt/twitter_shilling_bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

echo "✅ VPS setup complete!"
echo ""
echo "Next steps:"
echo "1. Copy your .env file to /opt/twitter_shilling_bot/"
echo "2. Start the bot:"
echo "   Option A (systemd): sudo systemctl start twitter-bot"
echo "   Option B (screen): screen -S twitter_bot python main.py"
echo "3. Monitor logs: tail -f logs/twitter_bot_\$(date +%Y-%m-%d).log"
echo "4. Enable auto-start: sudo systemctl enable twitter-bot"
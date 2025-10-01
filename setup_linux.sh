#!/bin/bash
echo "Creating virtual environment..."
python3 -m venv venv

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing requirements..."
pip install -r requirements.txt

echo "Setup complete!"
echo ""
echo "To start the bot:"
echo "1. Copy .env.example to .env and fill in your credentials"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python main.py"
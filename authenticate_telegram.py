#!/usr/bin/env python3
"""
Interactive Telegram Authentication Script
Run this script to authenticate your personal Telegram account for the bot.
"""

import asyncio
import sys
import os
from pyrogram import Client

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import config

async def authenticate_telegram():
    """Interactive Telegram authentication"""
    print("🔐 Telegram Authentication Setup")
    print("=" * 50)
    print()
    print("This script will help you authenticate your personal Telegram account.")
    print("You'll need to provide your phone number and verification code.")
    print()
    
    try:
        # Create Telegram client
        client = Client(
            "twitter_bot_session",
            api_id=int(config.telegram_api_id),
            api_hash=config.telegram_api_hash,
            workdir="."
        )
        
        print("📱 Connecting to Telegram...")
        await client.start()
        
        # Get user info
        me = await client.get_me()
        print(f"✅ Successfully authenticated!")
        print(f"👤 Logged in as: {me.first_name} {me.last_name or ''}")
        print(f"📞 Phone: {me.phone_number}")
        print(f"🆔 Username: @{me.username}")
        print()
        print("🎉 Authentication completed! You can now run the main bot.")
        
        await client.stop()
        return True
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        print()
        print("💡 Troubleshooting tips:")
        print("1. Make sure your phone number is correct")
        print("2. Check that you received the verification code")
        print("3. Ensure your internet connection is stable")
        print("4. Try again in a few minutes if rate limited")
        return False

if __name__ == "__main__":
    print("Starting Telegram authentication...")
    success = asyncio.run(authenticate_telegram())
    
    if success:
        print("\\n✅ Ready to run the bot! Use: python main.py")
    else:
        print("\\n❌ Authentication failed. Please try again.")
        sys.exit(1)
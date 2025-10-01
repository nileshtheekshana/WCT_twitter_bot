import os
from typing import Dict, Optional
from dotenv import load_dotenv
from loguru import logger


class Config:
    """Configuration loader for the Twitter Shilling Bot"""
    
    def __init__(self, env_file: str = ".env"):
        load_dotenv(env_file)
        self._validate_required_configs()
    
    def _validate_required_configs(self):
        """Validate that required environment variables are set"""
        required_vars = [
            "TELEGRAM_MAIN_CHANNEL_ID",
            "TELEGRAM_MAIN_GROUP_ID", 
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_NOTIFICATION_GROUP_ID",
            "TELEGRAM_USER_ID",
            "TELEGRAM_API_ID",
            "TELEGRAM_API_HASH",
            "AI_API_KEY",
            "TWITTER_CONSUMER_KEY",
            "TWITTER_CONSUMER_SECRET",
            "TWITTER_ACCESS_TOKEN",
            "TWITTER_ACCESS_TOKEN_SECRET",
            "TWITTER_BEARER_TOKEN"
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    # Telegram Configuration
    @property
    def telegram_main_channel_id(self) -> str:
        return os.getenv("TELEGRAM_MAIN_CHANNEL_ID")
    
    @property
    def telegram_main_group_id(self) -> str:
        return os.getenv("TELEGRAM_MAIN_GROUP_ID")
    
    @property
    def telegram_bot_token(self) -> str:
        return os.getenv("TELEGRAM_BOT_TOKEN")
    
    @property
    def telegram_notification_group_id(self) -> str:
        return os.getenv("TELEGRAM_NOTIFICATION_GROUP_ID")
    
    @property
    def telegram_user_id(self) -> str:
        return os.getenv("TELEGRAM_USER_ID")
    
    @property
    def telegram_api_id(self) -> str:
        return os.getenv("TELEGRAM_API_ID")
    
    @property
    def telegram_api_hash(self) -> str:
        return os.getenv("TELEGRAM_API_HASH")
    
    @property
    def comment_selection_timeout_minutes(self) -> int:
        return int(os.getenv("COMMENT_SELECTION_TIMEOUT_MINUTES", "45"))
    
    # AI Configuration
    @property
    def ai_api_key(self) -> str:
        return os.getenv("AI_API_KEY")
    
    @property
    def ai_model(self) -> str:
        return os.getenv("AI_MODEL", "llama-3.1-8b-instant")
    
    # Twitter Configuration - Main Account
    @property
    def twitter_main_config(self) -> Dict[str, str]:
        return {
            "consumer_key": os.getenv("TWITTER_CONSUMER_KEY"),
            "consumer_secret": os.getenv("TWITTER_CONSUMER_SECRET"),
            "access_token": os.getenv("TWITTER_ACCESS_TOKEN"),
            "access_token_secret": os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
            "client_id": os.getenv("TWITTER_CLIENT_ID"),
            "client_secret": os.getenv("TWITTER_CLIENT_SECRET"),
            "bearer_token": os.getenv("TWITTER_BEARER_TOKEN")
        }
    
    @property
    def twitter_main_username(self) -> Optional[str]:
        """Get the main Twitter account username for proper URLs"""
        return os.getenv("TWITTER_MAIN_USERNAME")
    
    # Twitter Configuration - All Accounts (for reading)
    @property
    def twitter_read_configs(self) -> list[Dict[str, str]]:
        configs = [self.twitter_main_config]  # Include main account for reading too
        
        for i in range(1, 6):  # Accounts 1-5
            suffix = str(i)
            config = {
                "consumer_key": os.getenv(f"TWITTER_CONSUMER_KEY{suffix}"),
                "consumer_secret": os.getenv(f"TWITTER_CONSUMER_SECRET{suffix}"),
                "access_token": os.getenv(f"TWITTER_ACCESS_TOKEN{suffix}"),
                "access_token_secret": os.getenv(f"TWITTER_ACCESS_TOKEN_SECRET{suffix}"),
                "client_id": os.getenv(f"TWITTER_CLIENT_ID{suffix}"),
                "client_secret": os.getenv(f"TWITTER_CLIENT_SECRET{suffix}"),
                "bearer_token": os.getenv(f"TWITTER_BEARER_TOKEN{suffix}")
            }
            
            # Only add if at least bearer token is available
            if config["bearer_token"]:
                configs.append(config)
        
        return configs
    
    # Application Settings
    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")
    
    @property
    def max_retries(self) -> int:
        return int(os.getenv("MAX_RETRIES", "3"))
    
    @property
    def rate_limit_delay(self) -> int:
        return int(os.getenv("RATE_LIMIT_DELAY", "60"))
    
    @property 
    def comment_selection_timeout_minutes(self) -> int:
        return int(os.getenv("COMMENT_SELECTION_TIMEOUT_MINUTES", "45"))


# Global config instance
config = Config()
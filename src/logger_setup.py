import sys
import os
from datetime import datetime
from loguru import logger
from pathlib import Path


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration with file and console output"""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Remove default logger
    logger.remove()
    
    # Add console logging with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # Add file logging - general log
    logger.add(
        "logs/twitter_bot_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=log_level,
        rotation="1 day",
        retention="30 days",
        compression="zip"
    )
    
    # Add file logging - error only
    logger.add(
        "logs/errors_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="1 day",
        retention="30 days",
        compression="zip"
    )
    
    # Add file logging - job activities
    logger.add(
        "logs/jobs_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO",
        rotation="1 day",
        retention="30 days",
        compression="zip",
        filter=lambda record: "JOB_ACTIVITY" in record["extra"]
    )
    
    logger.info("Logging system initialized")


def log_job_activity(message: str, extra_data: dict = None):
    """Log job-related activities to separate file"""
    extra = {"JOB_ACTIVITY": True}
    if extra_data:
        extra.update(extra_data)
    
    logger.bind(**extra).info(message)


def log_twitter_usage(account_name: str, action: str, remaining_reads: int = None, remaining_writes: int = None):
    """Log Twitter API usage for monitoring rate limits"""
    usage_data = {
        "account": account_name,
        "action": action,
        "timestamp": datetime.now().isoformat()
    }
    
    if remaining_reads is not None:
        usage_data["remaining_reads"] = remaining_reads
    if remaining_writes is not None:
        usage_data["remaining_writes"] = remaining_writes
    
    log_job_activity(f"Twitter API Usage: {action} with {account_name}", usage_data)
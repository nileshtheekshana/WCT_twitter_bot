import re
import asyncio
from typing import Optional, Dict, List
from urllib.parse import urlparse


class TextUtils:
    """Utility functions for text processing"""
    
    @staticmethod
    def extract_twitter_url(text: str) -> Optional[str]:
        """Extract Twitter/X URL from text"""
        # Patterns for both twitter.com and x.com
        patterns = [
            r'https?://(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/\d+',
            r'https?://(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/\d+\?[^\s]*'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    @staticmethod
    def extract_task_number(text: str) -> Optional[str]:
        """Extract task number from job post (e.g., R133 - REQUIRED TASK NUMBER [ 73 ])"""
        pattern = r'R(\d+)\s*-\s*(?:REQUIRED\s+)?TASK\s+NUMBER\s*\[\s*(\d+)\s*\]'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"R{match.group(1)} - Task {match.group(2)}"
        return None
    
    @staticmethod
    def extract_tweet_id(url: str) -> Optional[str]:
        """Extract tweet ID from Twitter URL"""
        pattern = r'/status/(\d+)'
        match = re.search(pattern, url)
        return match.group(1) if match else None
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean text for better processing"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove emojis and special characters for AI processing
        text = re.sub(r'[^\w\s\-.,!?:;()[\]{}"]', '', text)
        return text
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 280) -> str:
        """Truncate text to specified length"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."


class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    async def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = asyncio.get_event_loop().time()
        
        # Remove old calls outside time window
        self.calls = [call_time for call_time in self.calls 
                     if now - call_time < self.time_window]
        
        # If we're at the limit, wait
        if len(self.calls) >= self.max_calls:
            sleep_time = self.time_window - (now - self.calls[0]) + 1
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                # Clean up old calls again
                now = asyncio.get_event_loop().time()
                self.calls = [call_time for call_time in self.calls 
                             if now - call_time < self.time_window]
        
        # Record this call
        self.calls.append(now)


class RetryHelper:
    """Helper for retrying operations with exponential backoff"""
    
    @staticmethod
    async def retry_async(func, max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
        """Retry an async function with exponential backoff"""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    await asyncio.sleep(delay * (backoff ** attempt))
                    continue
                break
        
        raise last_exception
    
    @staticmethod
    def retry_sync(func, max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
        """Retry a sync function with exponential backoff"""
        import time
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    time.sleep(delay * (backoff ** attempt))
                    continue
                break
        
        raise last_exception


class JobDataExtractor:
    """Extract structured data from job posts"""
    
    @staticmethod
    def extract_job_data(text: str) -> Dict[str, str]:
        """Extract structured data from job post"""
        data = {}
        
        # Extract task number
        task_match = re.search(r'R(\d+)\s*-\s*(?:REQUIRED\s+)?TASK\s+NUMBER\s*\[\s*(\d+)\s*\]', text, re.IGNORECASE)
        if task_match:
            data['round'] = task_match.group(1)
            data['task_number'] = task_match.group(2)
            data['task_id'] = f"R{task_match.group(1)} - Task {task_match.group(2)}"
        
        # Extract date
        date_match = re.search(r'Date\s+([^\\n]+)', text, re.IGNORECASE)
        if date_match:
            data['date'] = date_match.group(1).strip()
        
        # Extract duration
        duration_match = re.search(r'Duration\s+([^\\n]+)', text, re.IGNORECASE)
        if duration_match:
            data['duration'] = duration_match.group(1).strip()
        
        # Extract title
        title_match = re.search(r'Title:\s*([^\\n]+)', text, re.IGNORECASE)
        if title_match:
            data['title'] = title_match.group(1).strip()
        
        # Extract link
        link_match = re.search(r'LINK:\s*(https?://[^\\s]+)', text, re.IGNORECASE)
        if link_match:
            data['link'] = link_match.group(1).strip()
        
        # Extract reward if present
        reward_match = re.search(r'Reward:\s*([^\\n]+)', text, re.IGNORECASE)
        if reward_match:
            data['reward'] = reward_match.group(1).strip()
        
        return data
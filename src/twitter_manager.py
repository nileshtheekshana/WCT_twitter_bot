import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import tweepy
from loguru import logger
from .config import config
from .utils import TextUtils, RetryHelper, RateLimiter
from .logger_setup import log_twitter_usage


class TwitterAPIManager:
    """Manages multiple Twitter API accounts with rate limiting"""
    
    def __init__(self):
        self.main_client = None
        self.read_clients = []
        self.current_read_index = 0
        self.usage_stats = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Twitter API clients (no API calls made)"""
        try:
            # Initialize main client (for writing only)
            main_config = config.twitter_main_config
            if self._validate_config(main_config):
                self.main_client = self._create_client(main_config, "main")
                logger.info("Main Twitter client initialized (no API test)")
            else:
                raise ValueError("Main Twitter API configuration is incomplete")
            
            # Initialize read clients (for reading only)
            read_configs = config.twitter_read_configs
            for i, read_config in enumerate(read_configs):
                if self._validate_config(read_config):
                    client = self._create_client(read_config, f"read_{i}")
                    self.read_clients.append(client)
                    logger.info(f"Twitter read client {i} initialized (no API test)")
                else:
                    logger.warning(f"Read client {i} configuration incomplete, skipping")
            
            if not self.read_clients:
                logger.warning("No read clients available, using main client for reading")
                self.read_clients = [self.main_client]
            
            logger.info(f"Twitter manager initialized with {len(self.read_clients)} read clients (ready for minimal API usage)")
            
        except Exception as e:
            logger.error(f"Failed to initialize Twitter clients: {e}")
            raise
    
    def _validate_config(self, config_dict: Dict[str, str]) -> bool:
        """Validate Twitter API configuration"""
        required_keys = ["consumer_key", "consumer_secret", "access_token", "access_token_secret", "bearer_token"]
        return all(config_dict.get(key) for key in required_keys)
    
    def _create_client(self, config_dict: Dict[str, str], client_name: str) -> tweepy.Client:
        """Create a Twitter API client"""
        client = tweepy.Client(
            bearer_token=config_dict["bearer_token"],
            consumer_key=config_dict["consumer_key"],
            consumer_secret=config_dict["consumer_secret"],
            access_token=config_dict["access_token"],
            access_token_secret=config_dict["access_token_secret"],
            wait_on_rate_limit=True
        )
        
        # Initialize usage stats
        self.usage_stats[client_name] = {
            "reads": 0,
            "writes": 0,
            "last_reset": asyncio.get_event_loop().time()
        }
        
        return client
    
    async def get_tweet_content(self, twitter_url: str) -> tuple[Optional[str], str]:
        """Get tweet content using exactly ONE API call per task"""
        tweet_id = TextUtils.extract_tweet_id(twitter_url)
        if not tweet_id:
            logger.error(f"Could not extract tweet ID from URL: {twitter_url}")
            return None, "none"
        
        # Use next client in rotation - SINGLE API CALL ONLY
        client = self._get_next_read_client()
        client_name = f"read_{self.current_read_index - 1}"
        
        try:
            log_twitter_usage(client_name, "get_tweet")
            
            # Single API call - no retries to minimize usage
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: client.get_tweet(
                    tweet_id, 
                    tweet_fields=["text", "author_id"]
                )
            )
            
            if response and response.data:
                content = TextUtils.clean_tweet_text(response.data.text)
                logger.info(f"✅ Tweet read with {client_name} (1 API call): {content[:100]}...")
                return content, client_name
            else:
                logger.error(f"❌ No tweet data returned from {client_name}")
                return None, client_name
                
        except Exception as e:
            logger.error(f"❌ Failed to read tweet with {client_name}: {e}")
            return None, client_name
    
    async def post_reply(self, tweet_id: str, reply_text: str, telegram_responder=None, job_data=None) -> Optional[str]:
        """Post a reply using main account, with 5th account fallback if approved"""
        try:
            if not self.main_client:
                logger.error("Main Twitter client not available")
                return None
            
            # Ensure reply text is within Twitter limits
            reply_text = TextUtils.truncate_text(reply_text, 280)
            
            # Try main account first
            result = await self._try_post_with_client(self.main_client, "main", tweet_id, reply_text)
            
            if result["success"]:
                return result["url"]
            elif (result["rate_limited"] or result["restricted"]) and telegram_responder and job_data:
                # Main account is rate limited or restricted - ask for approval to use 5th account
                restriction_type = "rate limited" if result["rate_limited"] else "restricted/suspended"
                logger.warning(f"🚫 Main account {restriction_type} - requesting approval for 5th account fallback")
                
                approved = await self._request_fallback_approval(telegram_responder, job_data, restriction_type)
                
                if approved:
                    # Use 5th account (index 4) as fallback
                    if len(self.read_clients) > 4:
                        fallback_client = self.read_clients[4]  # 5th account
                        fallback_result = await self._try_post_with_client(fallback_client, "account_5_fallback", tweet_id, reply_text)
                        
                        if fallback_result["success"]:
                            logger.info("✅ Successfully posted using 5th account fallback")
                            return fallback_result["url"]
                        else:
                            logger.error("❌ 5th account fallback also failed")
                            return None
                    else:
                        logger.error("❌ 5th account not available")
                        return None
                else:
                    logger.info("🚫 User denied 5th account fallback - task will fail")
                    return None
            else:
                logger.error(f"❌ Main account failed: {result.get('error', 'Unknown error')}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Error posting reply: {e}")
            return None
    
    async def _try_post_with_client(self, client: tweepy.Client, client_name: str, tweet_id: str, reply_text: str) -> Dict:
        """Try to post with a specific client and return detailed result"""
        try:
            log_twitter_usage(client_name, "post_reply")
            
            # Single API call
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.create_tweet(
                    text=reply_text,
                    in_reply_to_tweet_id=tweet_id
                )
            )
            
            if response and response.data:
                # Get username for proper URL
                try:
                    if client_name == "main":
                        username = getattr(config, 'twitter_main_username', None)
                        if not username:
                            user_info = await loop.run_in_executor(None, lambda: client.get_me())
                            username = user_info.data.username if user_info and user_info.data else "user"
                    else:
                        # For fallback account, try to get username or use generic
                        try:
                            user_info = await loop.run_in_executor(None, lambda: client.get_me())
                            username = user_info.data.username if user_info and user_info.data else "user"
                        except:
                            username = "user"
                    
                    reply_url = f"https://twitter.com/{username}/status/{response.data['id']}"
                except Exception as e:
                    logger.warning(f"Could not get username: {e}, using generic URL")
                    reply_url = f"https://twitter.com/user/status/{response.data['id']}"
                
                logger.info(f"✅ Reply posted with {client_name} (1 API call): {reply_url}")
                return {"success": True, "url": reply_url, "rate_limited": False, "restricted": False}
            else:
                logger.error(f"❌ No response data from {client_name}")
                return {"success": False, "error": "No response data", "rate_limited": False, "restricted": False}
                
        except tweepy.TooManyRequests:
            logger.warning(f"🚫 Rate limit exceeded for {client_name}")
            return {"success": False, "error": "Rate limit exceeded", "rate_limited": True, "restricted": False}
        except tweepy.Forbidden as e:
            # 403 Forbidden means account is restricted/suspended
            logger.warning(f"🚫 Account {client_name} is restricted/forbidden: {e}")
            return {"success": False, "error": f"Account restricted: {e}", "rate_limited": False, "restricted": True}
        except Exception as e:
            logger.error(f"❌ Error with {client_name}: {e}")
            return {"success": False, "error": str(e), "rate_limited": False, "restricted": False}
    
    async def _request_fallback_approval(self, telegram_responder, job_data: dict, restriction_type: str = "rate limited") -> bool:
        """Request approval from user to use 5th account fallback"""
        try:
            task_id = job_data.get('task_id', 'Unknown')
            
            message = f"⚠️ **{restriction_type.title()} Alert - {task_id}**\n\n"
            message += f"🚫 Main Twitter account is {restriction_type}\n"
            message += f"🔄 Can I use 5th account as fallback for posting?\n\n"
            message += f"**Reply with:**\n"
            message += f"• `yes` or `y` to approve 5th account\n"
            message += f"• `no` or `n` to deny (task will fail)\n\n"
            message += f"⏰ Waiting 5 minutes for your decision..."
            
            # Send approval request
            approval_sent = await telegram_responder.send_fallback_approval_request(message, job_data)
            
            if not approval_sent:
                logger.error("Failed to send approval request")
                return False
            
            # Wait for approval (5 minutes timeout)
            import asyncio
            try:
                approved = await asyncio.wait_for(
                    telegram_responder.wait_for_fallback_approval(task_id),
                    timeout=300  # 5 minutes
                )
                
                logger.info(f"📱 User {'approved' if approved else 'denied'} 5th account fallback")
                return approved
                
            except asyncio.TimeoutError:
                logger.warning("⏰ Fallback approval timeout - defaulting to deny")
                return False
                
        except Exception as e:
            logger.error(f"Error requesting fallback approval: {e}")
            return False
    
    def _get_next_read_client(self) -> tweepy.Client:
        """Get the next read client in rotation"""
        client = self.read_clients[self.current_read_index]
        self.current_read_index = (self.current_read_index + 1) % len(self.read_clients)
        return client
    
    # Removed retry methods to ensure exactly 1 API call per operation
    
    def get_usage_stats(self) -> Dict[str, Dict]:
        """Get current usage statistics for all clients"""
        return self.usage_stats.copy()
    
    # Removed test methods to eliminate unnecessary API calls
    # Clients will be validated only when used for actual tasks


class CommentGenerator:
    """Generate AI-powered realistic comments only - no templates"""
    
    def __init__(self, ai_validator=None):
        self.ai_validator = ai_validator
        # Remove all template comments - AI only
        logger.info("CommentGenerator initialized - AI-only mode (no templates)")
    
    async def generate_ai_comment(self, tweet_content: str) -> Optional[str]:
        """Generate AI-powered realistic comment"""
        try:
            if not self.ai_validator:
                logger.error("❌ AI validator not available - cannot generate comments")
                return None
            
            # Use AI to generate human-like comment
            prompt = f"""
Generate a realistic human-like Twitter reply to this tweet. Make it sound like a real person:

Tweet: "{tweet_content}"

Requirements:
- Sound natural and human-like
- Use casual internet language ("gonna", "tbh", "ngl", "af", etc.)
- 1-2 sentences max
- 50% chance to include 1 emoji (🔥💯🚀�💪🎯⚡✨👀🤔)
- Different tones: excited, skeptical, bullish, casual, curious, agreeing
- Small typos/slang are OK

Reply:"""
            
            ai_comment = await self.ai_validator.generate_comment(prompt)
            
            if ai_comment and len(ai_comment.strip()) > 0:
                logger.info(f"✅ AI generated comment: {ai_comment[:50]}...")
                return ai_comment.strip()
            else:
                logger.error("❌ AI failed to generate valid comment")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error generating AI comment: {e}")
            return None
    
    async def generate_multiple_ai_comments(self, tweet_content: str, count: int = 5) -> List[str]:
        """Generate exactly 5 AI comments using batch generation"""
        try:
            if not self.ai_validator:
                logger.error("❌ AI validator not available - cannot generate comments")
                return []
            
            # Use the AI validator's generate_comments method for batch generation
            comments = await self.ai_validator.generate_comments(tweet_content)
            
            if len(comments) == 0:
                logger.error("❌ AI failed to generate any comments - TASK WILL BE SKIPPED")
                return []
            elif len(comments) < 5:
                logger.warning(f"⚠️ Only generated {len(comments)}/5 AI comments")
            
            logger.info(f"✅ Generated {len(comments)} AI comments successfully")
            return comments[:5]  # Return exactly 5 comments
            
        except Exception as e:
            logger.error(f"❌ Error generating multiple AI comments: {e}")
            return []
    
    def _extract_themes(self, text: str) -> List[str]:
        """Extract key themes from tweet text"""
        # Simple keyword extraction
        import re
        
        # Common topics and their variations
        topic_keywords = {
            "AI": ["ai", "artificial intelligence", "machine learning", "automation"],
            "crypto": ["crypto", "bitcoin", "blockchain", "ethereum", "defi"],
            "business": ["business", "startup", "entrepreneur", "growth", "strategy"],
            "technology": ["tech", "technology", "software", "development", "innovation"],
            "marketing": ["marketing", "branding", "social media", "content", "advertising"],
            "investing": ["investing", "stocks", "market", "finance", "portfolio"],
            "productivity": ["productivity", "efficiency", "time management", "workflow"],
            "leadership": ["leadership", "management", "team", "culture", "vision"]
        }
        
        text_lower = text.lower()
        found_themes = []
        
        for theme, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                found_themes.append(theme)
        
        return found_themes if found_themes else ["this topic"]
    
    async def generate_and_select_comment(self, tweet_content: str, job_data: dict, twitter_url: str, account_used: str, telegram_responder=None) -> tuple:
        """Generate AI comments and handle interactive selection - skip task if AI fails"""
        try:
            # Generate 5 AI comments - NO TEMPLATES
            all_comments = await self.generate_multiple_ai_comments(tweet_content, 5)
            
            if not all_comments or len(all_comments) == 0:
                logger.error("❌ NO AI COMMENTS GENERATED - TASK WILL BE SKIPPED")
                return None, []  # This will cause the task to be skipped
            
            logger.info(f"✅ Generated {len(all_comments)} AI comments for interactive selection")
            
            # MANDATORY: Send to Telegram for user selection
            if telegram_responder:
                selected_comment = await self._handle_interactive_selection(
                    all_comments, job_data, telegram_responder, account_used, twitter_url, tweet_content
                )
            else:
                logger.error("❌ No Telegram responder - cannot get user selection")
                return None, all_comments
            
            return selected_comment, all_comments
            
        except Exception as e:
            logger.error(f"❌ Error in AI comment generation and selection: {e}")
            return None, []
    
    async def _handle_interactive_selection(self, comments: List[str], job_data: dict, telegram_responder, account_used: str, twitter_url: str, tweet_content: str) -> str:
        """Handle interactive comment selection via Telegram - MANDATORY USER INTERACTION"""
        try:
            logger.info(f"📱 Sending {len(comments)} comments to Telegram for user selection...")
            
            # Use the existing telegram selection system with tweet content
            selected_comment = await telegram_responder.request_comment_selection(
                comment_options=comments,
                job_data=job_data,
                tweet_url=twitter_url,
                tweet_text=tweet_content,  # Include actual tweet content
                account_used=account_used
            )
            
            logger.info(f"✅ User selected comment via Telegram: {selected_comment[:50]}...")
            return selected_comment
            
        except Exception as e:
            logger.error(f"❌ Error in interactive selection: {e}")
            # If interactive selection fails, still don't auto-select
            # Let the task fail so user knows there's an issue
            raise e


class TextUtils:
    """Utility functions for text processing"""
    
    @staticmethod
    def truncate_text(text: str, max_length: int) -> str:
        """Truncate text to maximum length"""
        if len(text) <= max_length:
            return text
        
        # Try to truncate at word boundary
        truncated = text[:max_length]
        last_space = truncated.rfind(' ')
        
        if last_space > max_length * 0.8:  # If we can find a space in the last 20%
            return truncated[:last_space] + "..."
        else:
            return truncated[:max_length-3] + "..."
    
    @staticmethod
    def clean_tweet_text(text: str) -> str:
        """Clean tweet text for processing"""
        import re
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    @staticmethod
    def extract_tweet_id(twitter_url: str) -> Optional[str]:
        """Extract tweet ID from Twitter URL"""
        import re
        
        # Handle both twitter.com and x.com URLs
        patterns = [
            r'(?:twitter\.com|x\.com)/.+/status/(\d+)',
            r'(?:twitter\.com|x\.com)/.*?/status/(\d+)',
            r'/status/(\d+)',
            r'status/(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, twitter_url)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def extract_twitter_url(text: str) -> Optional[str]:
        """Extract Twitter URL from text"""
        import re
        
        # Pattern to match Twitter/X URLs
        pattern = r'https?://(?:twitter\.com|x\.com)/[^\s]+'
        match = re.search(pattern, text)
        
        if match:
            return match.group(0)
        
        return None


class RetryHelper:
    """Helper for retry logic"""
    
    @staticmethod
    async def retry_async(func, max_retries: int = 3, delay: float = 1.0):
        """Retry an async function with exponential backoff"""
        import asyncio
        
        for attempt in range(max_retries):
            try:
                return await func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                
                wait_time = delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)


def log_twitter_usage(account_name: str, action: str):
    """Log Twitter API usage for tracking - exactly 2 API calls per task"""
    logger.info(f"🔥 API CALL #{len(usage_stats)+1} - Account: {account_name}, Action: {action}")
    usage_stats[f"{account_name}_{action}_{len(usage_stats)}"] = {
        "account": account_name,
        "action": action,
        "timestamp": datetime.now().isoformat()
    }


# Global usage statistics
usage_stats = {}


def create_twitter_manager():
    """Factory function to create TwitterAPIManager instance"""
    return TwitterAPIManager()


def create_comment_generator(ai_validator=None, telegram_responder=None):
    """Factory function to create CommentGenerator instance with AI validator"""
    return CommentGenerator(ai_validator)

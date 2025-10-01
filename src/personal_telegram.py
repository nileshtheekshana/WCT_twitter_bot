import asyncio
from typing import Optional, Dict, Any
from pyrogram import Client, filters, types
from pyrogram.handlers import MessageHandler
from loguru import logger
from .config import config
from .utils import JobDataExtractor
from .logger_setup import log_job_activity


class PersonalTelegramClient:
    """Personal Telegram client for submitting comments and monitoring channel messages in group"""
    
    def __init__(self, job_callback=None):
        self.client = None
        self.job_callback = job_callback
        self.is_running = False
        self.channel_messages = {}  # Store channel message IDs mapped to group message IDs
        
    async def initialize(self):
        """Initialize the personal Telegram client with authentication handling"""
        try:
            self.client = Client(
                "twitter_bot_session",
                api_id=int(config.telegram_api_id),
                api_hash=config.telegram_api_hash,
                workdir="."
            )
            
            # Add message handler for monitoring forwarded messages from channel
            self.client.add_handler(
                MessageHandler(
                    self._handle_group_message,
                    filters.chat(int(config.telegram_main_group_id))
                )
            )

            # Try to start with better error handling
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Starting personal Telegram client (attempt {attempt + 1}/{max_retries})...")
                    await self.client.start()
                    
                    # Get user info to verify connection
                    me = await self.client.get_me()
                    logger.info(f"Personal Telegram client initialized for user: {me.first_name} (@{me.username})")
                    return True
                    
                except Exception as e:
                    if "AUTH_KEY_UNREGISTERED" in str(e) or "SESSION_PASSWORD_NEEDED" in str(e):
                        logger.error(f"Authentication required for personal Telegram client")
                        logger.error(f"Please run the bot interactively to authenticate")
                        logger.error(f"The bot will continue without personal Telegram monitoring")
                        return False
                    elif attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {e}")
                        await asyncio.sleep(2)
                        continue
                    else:
                        raise e
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to initialize personal Telegram client: {e}")
            logger.error("The bot will continue without personal Telegram monitoring")
            return False
    
    async def start_monitoring(self):
        """Start monitoring for forwarded channel messages in the group"""
        try:
            if not self.client:
                await self.initialize()
            
            self.is_running = True
            logger.info(f"Started monitoring group {config.telegram_main_group_id} for channel messages")
            
            # Keep the client running until stopped
            while self.is_running:
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in personal Telegram monitoring: {e}")
            raise
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        try:
            if self.client and self.is_running:
                self.is_running = False
                await self.client.stop()
                logger.info("Stopped personal Telegram monitoring")
        except Exception as e:
            logger.error(f"Error stopping personal Telegram monitoring: {e}")
    
    async def _handle_group_message(self, client: Client, message: types.Message):
        """Handle messages in the group, focusing on forwarded channel messages"""
        try:
            # Check if this is a forwarded message from our target channel
            if (message.forward_from_chat and 
                str(message.forward_from_chat.id) == config.telegram_main_channel_id):
                
                logger.info(f"Detected forwarded message from channel in group")
                
                # Store the mapping: channel message ID -> group message ID
                channel_msg_id = message.forward_from_message_id
                group_msg_id = message.id
                
                self.channel_messages[channel_msg_id] = {
                    'group_message_id': group_msg_id,
                    'text': message.text,
                    'timestamp': message.date
                }
                
                # Extract job data
                if message.text:
                    job_data = JobDataExtractor.extract_job_data(message.text)
                    job_data['channel_message_id'] = channel_msg_id
                    job_data['group_message_id'] = group_msg_id
                    job_data['message_text'] = message.text
                    job_data['timestamp'] = message.date.isoformat() if message.date else None
                    
                    # Log the activity
                    log_job_activity(
                        f"Channel message forwarded to group: {job_data.get('task_id', 'Unknown')}",
                        job_data
                    )
                    
                    # Call the job callback if provided
                    if self.job_callback:
                        await asyncio.create_task(
                            self._safe_callback(message.text, job_data)
                        )
            
        except Exception as e:
            logger.error(f"Error handling group message: {e}")
    
    async def _safe_callback(self, message_text: str, job_data: dict):
        """Safely execute the job callback"""
        try:
            if asyncio.iscoroutinefunction(self.job_callback):
                await self.job_callback(message_text, job_data)
            else:
                self.job_callback(message_text, job_data)
        except Exception as e:
            logger.error(f"Error in job callback: {e}")
    
    async def submit_comment_link(self, comment_url: str, job_data: dict) -> bool:
        """Submit comment link as a reply using personal account"""
        try:
            if not self.client:
                logger.error("Personal Telegram client not initialized")
                return False
            
            # Get the group message ID to reply to
            group_message_id = job_data.get('group_message_id')
            
            if group_message_id:
                # Send as reply to the forwarded message in the group
                await self.client.send_message(
                    chat_id=int(config.telegram_main_group_id),
                    text=comment_url,
                    reply_to_message_id=group_message_id
                )
                logger.info(f"Successfully submitted comment link as reply to group message {group_message_id}")
            else:
                # Fallback: send without reply
                await self.client.send_message(
                    chat_id=int(config.telegram_main_group_id),
                    text=comment_url
                )
                logger.info("Successfully submitted comment link (no reply - group message ID not found)")
            
            task_id = job_data.get('task_id', 'Unknown Task')
            log_job_activity(f"Submitted comment link for {task_id} using personal account", {"comment_url": comment_url})
            
            return True
            
        except Exception as e:
            logger.error(f"Error submitting comment link with personal client: {e}")
            return False
    
    async def send_comment_options(self, comment_options: list, job_data: dict, tweet_url: str) -> str:
        """
        Send comment options to user for selection and wait for response
        Returns: selected comment
        """
        try:
            if not self.client:
                logger.error("Personal Telegram client not initialized")
                return comment_options[0]  # Return first as fallback
            
            # Format the options message
            task_id = job_data.get('task_id', 'Unknown')
            options_message = f"📝 **Comment Options for {task_id}**\n\n"
            options_message += f"Tweet: {tweet_url}\n\n"
            options_message += f"**Option 1:** {comment_options[0]}\n\n"
            options_message += f"**Option 2:** {comment_options[1]}\n\n"
            options_message += f"Reply with **1** or **2** to choose your comment"
            
            # Send options to user's private chat (using user ID)
            await self.client.send_message(
                chat_id=int(config.telegram_user_id),
                text=options_message
            )
            
            logger.info(f"Sent comment options to user for {task_id}")
            
            # For now, return first option as default
            # TODO: Implement actual user response waiting
            selected = comment_options[0]
            logger.info(f"Using default selection: {selected}")
            
            return selected
            
        except Exception as e:
            logger.error(f"Error sending comment options: {e}")
            return comment_options[0]  # Return first as fallback
    
    async def send_test_message(self, test_message: str) -> bool:
        """Send a test message to verify the client is working"""
        try:
            if not self.client:
                await self.initialize()
            
            await self.client.send_message(
                chat_id=int(config.telegram_main_group_id),
                text=test_message
            )
            
            logger.info("Test message sent successfully with personal client")
            return True
            
        except Exception as e:
            logger.error(f"Error sending test message: {e}")
            return False


# Factory function
def create_personal_telegram_client(job_callback=None) -> PersonalTelegramClient:
    """Create and return a personal Telegram client instance"""
    return PersonalTelegramClient(job_callback)
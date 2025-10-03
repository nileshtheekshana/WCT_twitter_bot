import asyncio
import signal
import sys
from datetime import datetime
from typing import Optional
from loguru import logger

# Import our modules
from src.config import config
from src.logger_setup import setup_logging, log_job_activity
from src.ai_validator import create_ai_validator
from src.twitter_manager import create_twitter_manager, create_comment_generator
from src.telegram_manager import (
    create_telegram_responder, 
    create_report_generator
)
from src.personal_telegram import PersonalTelegramClient
from src.utils import TextUtils


class TwitterShillingBot:
    """Main orchestrator for the Twitter Shilling Bot"""
    
    def __init__(self):
        self.ai_validator = None
        self.twitter_manager = None
        self.comment_generator = None
        self.telegram_responder = None
        self.report_generator = None
        self.personal_telegram = None
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize all components"""
        try:
            logger.info("Initializing Twitter Shilling Bot...")
            
            # Initialize AI validator
            self.ai_validator = create_ai_validator()
            logger.info("AI validator initialized")
            
            # Initialize Twitter manager
            self.twitter_manager = create_twitter_manager()
            logger.info("Twitter manager initialized")
            
            # Skip Twitter client testing during startup to avoid rate limits
            # Clients will be tested when first used
            logger.info("Skipping Twitter client test during startup to preserve API quota")
            
            # Initialize Telegram components first
            self.telegram_responder = create_telegram_responder(shutdown_callback=self._initiate_shutdown)
            await self.telegram_responder.initialize()  # Initialize async
            self.report_generator = create_report_generator()
            await self.report_generator.initialize()  # Initialize async
            
            # Start telegram responder polling for message handling
            await self.telegram_responder.start_polling()
            
            # Initialize comment generator with telegram responder
            self.comment_generator = create_comment_generator(self.ai_validator, self.telegram_responder)
            logger.info("Comment generator initialized")
            
            # Initialize personal Telegram client for monitoring and submissions
            self.personal_telegram = PersonalTelegramClient(self._handle_new_job)
            telegram_initialized = await self.personal_telegram.initialize()
            
            if telegram_initialized:
                logger.info("Personal Telegram client initialized")
            else:
                logger.warning("Personal Telegram client failed to initialize - continuing without it")
                self.personal_telegram = None
            
            logger.info("Telegram components initialized")
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def start(self):
        """Start the bot"""
        try:
            if not hasattr(self, 'ai_validator') or not self.ai_validator:
                await self.initialize()
            
            self.is_running = True
            logger.info("Starting Twitter Shilling Bot...")
            
            # Set up signal handlers for graceful shutdown
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, self._signal_handler)
            
            # Start monitoring Telegram with personal client if available
            if self.personal_telegram:
                monitor_task = asyncio.create_task(self.personal_telegram.start_monitoring())
                logger.info("🤖 Twitter Shilling Bot is now running! Monitoring for jobs...")
            else:
                logger.warning("🤖 Twitter Shilling Bot is running but without personal Telegram monitoring")
                logger.warning("You may need to authenticate Telegram manually")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            # Cancel monitoring task
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the bot gracefully"""
        if not self.is_running:
            return
            
        logger.info("Shutting down Twitter Shilling Bot...")
        self.is_running = False
        
        if self.personal_telegram:
            await self.personal_telegram.stop_monitoring()
        
        if self.telegram_responder:
            await self.telegram_responder.stop_polling()
        
        logger.info("Bot shutdown complete")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()
    
    async def _initiate_shutdown(self):
        """Initiate bot shutdown via Telegram command"""
        logger.info("Shutdown initiated via Telegram command")
        self.shutdown_event.set()
    
    async def _handle_new_job(self, message_text: str, job_data: dict):
        """Handle a new job message from Telegram"""
        start_time = datetime.now()
        processing_data = {
            'task_id': job_data.get('task_id', 'Unknown'),
            'timestamp': start_time.isoformat(),
            'success': False,
            'errors': []
        }
        
        try:
            logger.info(f"Processing new job: {job_data.get('task_id', 'Unknown')}")
            
            # Step 1: Validate if it's a valid Twitter job
            is_valid, reason = await self.ai_validator.is_valid_twitter_job(message_text)
            
            if not is_valid:
                logger.info(f"Skipping invalid job: {reason}")
                log_job_activity(f"Skipped job - {reason}", job_data)
                return
            
            logger.info(f"Valid Twitter job detected: {reason}")
            log_job_activity(f"Valid job detected: {job_data.get('task_id')}", job_data)
            
            # Step 2: Extract Twitter URL
            twitter_url = TextUtils.extract_twitter_url(message_text)
            if not twitter_url:
                error_msg = "No Twitter URL found in job post"
                processing_data['errors'].append(error_msg)
                await self._handle_job_error(error_msg, job_data)
                return
            
            logger.info(f"Extracted Twitter URL: {twitter_url}")
            processing_data['twitter_url'] = twitter_url
            
            # Step 3: Get tweet content
            tweet_content, account_used = await self.twitter_manager.get_tweet_content(twitter_url)
            if not tweet_content:
                error_msg = "Failed to read tweet content"
                processing_data['errors'].append(error_msg)
                await self._handle_job_error(error_msg, job_data)
                return
            
            logger.info(f"Retrieved tweet content using {account_used}: {tweet_content[:100]}...")
            processing_data['tweet_content'] = tweet_content
            processing_data['account_used'] = account_used
            
            # Step 4: Generate AI comments and handle interactive selection
            selected_comment, all_comments = await self.comment_generator.generate_and_select_comment(
                tweet_content, 
                job_data,
                twitter_url,
                account_used,
                self.telegram_responder  # Pass telegram responder for interactive selection
            )
            
            # Check if task was skipped by user or AI failed to generate comments
            if not selected_comment or selected_comment is None:
                error_msg = "⏭️ TASK SKIPPED - User requested skip or AI failed to generate comments"
                processing_data['errors'].append(error_msg)
                await self._handle_job_error(error_msg, job_data)
                logger.warning("🚫 Task skipped by user or due to AI comment generation failure")
                return
            
            processing_data['selected_comment'] = selected_comment
            processing_data['all_comments'] = all_comments
            processing_data['unused_comments'] = [c for c in all_comments if c != selected_comment]
            
            logger.info(f"✅ AI comment selected: {selected_comment}")
            
            # Step 5: Post the reply with fallback support
            tweet_id = TextUtils.extract_tweet_id(twitter_url)
            comment_url = await self.twitter_manager.post_reply(
                tweet_id, 
                selected_comment, 
                self.telegram_responder,  # For fallback approval
                job_data  # For task identification
            )
            
            if not comment_url:
                error_msg = "Failed to post reply to Twitter"
                processing_data['errors'].append(error_msg)
                await self._handle_job_error(error_msg, job_data)
                return
            
            logger.info(f"Posted reply successfully: {comment_url}")
            processing_data['comment_url'] = comment_url
            
            # Step 6: Submit to Telegram group using personal account
            submission_success = await self.personal_telegram.submit_comment_link(comment_url, job_data)
            
            if not submission_success:
                error_msg = "Failed to submit comment link to Telegram"
                processing_data['errors'].append(error_msg)
                logger.warning(error_msg)
            
            # Step 7: Generate final report
            processing_data['success'] = True
            processing_data['processing_time'] = str(datetime.now() - start_time)
            processing_data['api_usage'] = self.twitter_manager.get_usage_stats()
            
            await self.report_generator.send_completion_report(processing_data)
            
            logger.info(f"Successfully completed job: {job_data.get('task_id')}")
            log_job_activity(f"Job completed successfully: {job_data.get('task_id')}", processing_data)
            
        except Exception as e:
            error_msg = f"Unexpected error processing job: {str(e)}"
            processing_data['errors'].append(error_msg)
            logger.error(error_msg)
            await self._handle_job_error(error_msg, job_data, processing_data)
    
    async def _handle_job_error(self, error_message: str, job_data: dict, processing_data: dict = None):
        """Handle job processing errors"""
        try:
            # Send error notification
            await self.telegram_responder.send_error_notification(error_message, job_data)
            
            # Send error report if we have processing data
            if processing_data:
                processing_data['success'] = False
                processing_data['processing_time'] = str(datetime.now() - datetime.fromisoformat(processing_data.get('timestamp', datetime.now().isoformat())))
                await self.report_generator.send_completion_report(processing_data)
            
            log_job_activity(f"Job failed: {job_data.get('task_id', 'Unknown')} - {error_message}", job_data)
            
        except Exception as e:
            logger.error(f"Error handling job error: {e}")


async def main():
    """Main entry point"""
    try:
        # Setup logging
        setup_logging(config.log_level)
        
        logger.info("Starting Twitter Shilling Bot application...")
        
        # Create and start the bot
        bot = TwitterShillingBot()
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
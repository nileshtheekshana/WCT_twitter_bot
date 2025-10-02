import asyncio
from typing import Callable, Optional, List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from loguru import logger
from .config import config
from .utils import TextUtils, JobDataExtractor
from .logger_setup import log_job_activity
import random
import time


class TelegramMonitor:
    """Monitors Telegram channel for new job posts"""
    
    def __init__(self, job_callback: Callable[[str, dict], None]):
        self.app = None
        self.job_callback = job_callback
        self.is_running = False
        self.last_message_id = None
        
    async def start_monitoring(self):
        """Start monitoring the Telegram channel"""
        try:
            self.app = Application.builder().token(config.telegram_bot_token).build()
            
            # Add message handler for the main channel
            channel_filter = filters.Chat(chat_id=int(config.telegram_main_channel_id))
            message_handler = MessageHandler(
                channel_filter & filters.TEXT,
                self._handle_channel_message
            )
            self.app.add_handler(message_handler)
            
            # Start the application
            await self.app.initialize()
            await self.app.start()
            
            self.is_running = True
            logger.info(f"Started monitoring Telegram channel: {config.telegram_main_channel_id}")
            
            # Start polling (v20+ API)
            await self.app.run_polling()
            
        except Exception as e:
            logger.error(f"Error starting Telegram monitor: {e}")
            self.is_running = False
            raise
    
    async def stop_monitoring(self):
        """Stop monitoring the Telegram channel"""
        try:
            if self.app and self.is_running:
                await self.app.stop()
                await self.app.shutdown()
                self.is_running = False
                logger.info("Stopped monitoring Telegram channel")
        except Exception as e:
            logger.error(f"Error stopping Telegram monitor: {e}")
    
    async def _handle_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new messages from the monitored channel"""
        try:
            message = update.message or update.channel_post
            if not message or not message.text:
                return
            
            # Skip if we've already processed this message
            if self.last_message_id and message.message_id <= self.last_message_id:
                return
            
            self.last_message_id = message.message_id
            
            message_text = message.text
            logger.info(f"New message received from channel: {message_text[:100]}...")
            
            # Extract job data
            job_data = JobDataExtractor.extract_job_data(message_text)
            job_data['message_id'] = message.message_id
            job_data['message_text'] = message_text
            job_data['timestamp'] = message.date.isoformat() if message.date else None
            
            # Log the activity
            log_job_activity(
                f"New message from channel: {job_data.get('task_id', 'Unknown')}",
                job_data
            )
            
            # Call the job callback
            if self.job_callback:
                await asyncio.create_task(
                    self._safe_callback(message_text, job_data)
                )
                
        except Exception as e:
            logger.error(f"Error handling channel message: {e}")
    
    async def _safe_callback(self, message_text: str, job_data: dict):
        """Safely execute the job callback"""
        try:
            if asyncio.iscoroutinefunction(self.job_callback):
                await self.job_callback(message_text, job_data)
            else:
                self.job_callback(message_text, job_data)
        except Exception as e:
            logger.error(f"Error in job callback: {e}")


class TelegramResponder:
    """Handles responding to Telegram messages and sending reports"""
    
    def __init__(self):
        self.app = None
        self.pending_selections = {}  # Track pending comment selections
        self.pending_fallback_approvals = {}  # Track pending fallback approvals
        self.polling_task = None  # Track the polling task
        # Don't initialize app in __init__, do it async later
    
    async def initialize(self):
        """Initialize the Telegram application asynchronously"""
        if self.app is None:
            await self._initialize_app()
    
    async def _initialize_app(self):
        """Initialize the Telegram application"""
        try:
            # Try using the most basic approach for v20+
            from telegram.ext import ApplicationBuilder
            
            builder = ApplicationBuilder()
            builder.token(config.telegram_bot_token)
            self.app = builder.build()
            
            # Add message handler for comment selection responses
            selection_handler = MessageHandler(
                filters.Chat(chat_id=int(config.telegram_notification_group_id)) & filters.TEXT,
                self._handle_selection_response
            )
            self.app.add_handler(selection_handler)
            logger.info(f"✅ Added text selection handler for chat {config.telegram_notification_group_id}")
            
            # Add callback query handler for inline button selections
            callback_handler = CallbackQueryHandler(self._handle_button_callback)
            self.app.add_handler(callback_handler)
            logger.info("✅ Added button callback handler for all chats")
            
            # Add message handler for fallback approval responses  
            fallback_handler = MessageHandler(
                filters.Chat(chat_id=int(config.telegram_notification_group_id)) & filters.TEXT,
                self._handle_fallback_response
            )
            self.app.add_handler(fallback_handler)
            logger.info(f"✅ Added fallback approval handler for chat {config.telegram_notification_group_id}")
            
            logger.info("Telegram responder initialized")
        except Exception as e:
            logger.error(f"Error initializing Telegram responder: {e}")
            raise
    
    async def send_test_message(self):
        """Send a test message to verify bot connectivity"""
        try:
            if not self.app:
                await self.initialize()
            
            test_message = "🔧 <b>Bot Test Message</b>\n\n"
            test_message += "If you can see this, the bot can send messages.\n"
            test_message += "Please reply with 'test' to verify message reception."
            
            await self.app.bot.send_message(
                chat_id=int(config.telegram_notification_group_id),
                text=test_message,
                parse_mode='HTML'
            )
            
            logger.info("✅ Test message sent successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to send test message: {e}")
    
    async def start_polling(self):
        """Start polling for incoming messages"""
        try:
            if not self.app:
                await self.initialize()
            
            # In v22+, we need to use the new async approach
            await self.app.initialize()
            await self.app.start()
            
            # Start the updater as a background task
            self.polling_task = asyncio.create_task(self.app.updater.start_polling())
            logger.info("Telegram responder polling started successfully")
            
        except Exception as e:
            logger.error(f"Error starting Telegram responder polling: {e}")
            raise
    
    async def stop_polling(self):
        """Stop polling"""
        try:
            # Cancel the polling task if it exists
            if hasattr(self, 'polling_task') and self.polling_task:
                self.polling_task.cancel()
                try:
                    await self.polling_task
                except asyncio.CancelledError:
                    pass
                    
            if self.app:
                await self.app.stop()
                logger.info("Telegram responder polling stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram responder polling: {e}")
    
    async def _handle_selection_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user selection responses for comment choices"""
        try:
            logger.info(f"🔥 TEXT MESSAGE RECEIVED! Update: {update}")
            
            message = update.message
            if not message:
                logger.info("❌ No message in update")
                return
                
            if not message.text:
                logger.info("❌ No text in message")
                return
            
            text = message.text.strip()
            chat_id = message.chat_id
            user_id = message.from_user.id if message.from_user else "Unknown"
            
            logger.info(f"📱 TEXT: '{text}' from user {user_id} in chat {chat_id}")
            logger.info(f"📱 Expected chat: {config.telegram_notification_group_id}")
            logger.info(f"📱 Pending selections: {list(self.pending_selections.keys())}")
            
            # Check if it's a number between 1-5
            try:
                option_number = int(text)
                if not (1 <= option_number <= 5):
                    logger.info(f"❌ Number {option_number} not in range 1-5")
                    return  # Ignore invalid numbers
                logger.info(f"✅ Valid option number: {option_number}")
            except ValueError:
                logger.info(f"❌ '{text}' is not a number")
                return  # Ignore non-numeric messages
            
            # Find the pending selection this might be responding to
            for task_id, selection_data in self.pending_selections.items():
                if selection_data.get('completed', False):
                    logger.info(f"⏭️ Skipping completed selection: {task_id}")
                    continue  # Skip already completed selections
                
                logger.info(f"✅ Processing selection for task: {task_id}")
                
                # Mark as completed with the selected option
                selection_data['completed'] = True
                selection_data['selected_option'] = option_number - 1  # Convert to 0-based index
                
                # Send confirmation
                selected_comment = selection_data['comments'][option_number - 1]
                confirmation_message = f"✅ <b>Selection Confirmed for {task_id}</b>\n\n"
                confirmation_message += f"You chose Option {option_number}:\n<code>{selected_comment}</code>\n\n"
                confirmation_message += f"🚀 Proceeding to post this reply..."
                
                await self.app.bot.send_message(
                    chat_id=int(config.telegram_notification_group_id),
                    text=confirmation_message,
                    parse_mode='HTML'
                )
                
                logger.info(f"📱 User selected option {option_number} for {task_id} via text message")
                break
                
        except Exception as e:
            logger.error(f"Error handling selection response: {e}")
    
    async def _handle_button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callback for comment selection"""
        try:
            logger.info(f"🔥 Button callback received! Data: {update.callback_query.data}")
            
            query = update.callback_query
            await query.answer()  # Acknowledge the button press
            
            callback_data = query.data
            logger.info(f"Processing callback data: {callback_data}")
            
            # Parse callback data: "select_{task_id}_{option_index}"
            if callback_data.startswith('select_'):
                parts = callback_data.split('_')
                logger.info(f"Callback parts: {parts}")
                
                if len(parts) >= 3:
                    task_id = '_'.join(parts[1:-1])  # Handle task IDs with underscores
                    option_index = int(parts[-1])
                    
                    logger.info(f"Parsed task_id: {task_id}, option_index: {option_index}")
                    logger.info(f"Pending selections: {list(self.pending_selections.keys())}")
                    
                    # Check if this task is still pending
                    if task_id in self.pending_selections:
                        selection_data = self.pending_selections[task_id]
                        
                        if not selection_data['completed']:
                            # Mark as completed
                            selection_data['completed'] = True
                            selection_data['selected_option'] = option_index
                            
                            # Get the selected comment
                            selected_comment = selection_data['comments'][option_index]
                            
                            # Send confirmation message
                            await query.edit_message_text(
                                text=f"✅ <b>Selection Confirmed for {task_id}</b>\n\n"
                                     f"You selected Option {option_index + 1}:\n"
                                     f"<code>{selected_comment}</code>\n\n"
                                     f"🚀 Proceeding to post this reply...",
                                parse_mode='HTML'
                            )
                            
                            logger.info(f"📱 User selected option {option_index + 1} for {task_id} via button click")
                        else:
                            logger.warning(f"Selection for {task_id} already completed")
                            await query.edit_message_text(
                                text=f"⚠️ Selection for {task_id} has already been completed.",
                                parse_mode='HTML'
                            )
                    else:
                        logger.error(f"Task {task_id} not found in pending selections")
                        await query.edit_message_text(
                            text=f"⚠️ Selection for {task_id} has expired or is no longer available.",
                            parse_mode='HTML'
                        )
                else:
                    logger.error(f"Invalid callback data format: {callback_data}")
            else:
                logger.warning(f"Callback data doesn't start with 'select_': {callback_data}")
            
        except Exception as e:
            logger.error(f"Error handling button callback: {e}")
            try:
                await update.callback_query.edit_message_text(
                    text="❌ Error processing your selection. Please try again.",
                    parse_mode='HTML'
                )
            except:
                pass
    
    async def send_fallback_approval_request(self, message: str, job_data: dict) -> bool:
        """Send request for 5th account fallback approval"""
        try:
            if not self.app:
                logger.error("Telegram app not initialized")
                return False
            
            task_id = job_data.get('task_id', 'Unknown')
            
            # Store the pending approval
            self.pending_fallback_approvals[task_id] = {
                'approved': None,
                'start_time': time.time()
            }
            
            # Send to notification group
            result = await self.app.bot.send_message(
                chat_id=int(config.telegram_notification_group_id),
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"📱 Sent fallback approval request for {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending fallback approval request: {e}")
            return False
    
    async def wait_for_fallback_approval(self, task_id: str) -> bool:
        """Wait for user approval for fallback account usage"""
        try:
            import asyncio
            
            # Poll for approval every 2 seconds
            for _ in range(150):  # 5 minutes = 300 seconds / 2
                if task_id in self.pending_fallback_approvals:
                    approval_data = self.pending_fallback_approvals[task_id]
                    if approval_data['approved'] is not None:
                        approved = approval_data['approved']
                        # Clean up
                        del self.pending_fallback_approvals[task_id]
                        return approved
                
                await asyncio.sleep(2)
            
            # Timeout
            if task_id in self.pending_fallback_approvals:
                del self.pending_fallback_approvals[task_id]
            
            return False
            
        except Exception as e:
            logger.error(f"Error waiting for fallback approval: {e}")
            return False
    
    async def _handle_fallback_response(self, update, context):
        """Handle user's fallback approval response"""
        try:
            message = update.message
            if not message or not message.text:
                return
            
            text = message.text.strip().lower()
            
            # Check for approval/denial keywords
            if text in ['yes', 'y', 'approve', 'ok']:
                approval = True
            elif text in ['no', 'n', 'deny', 'cancel']:
                approval = False
            else:
                return  # Not a fallback response
            
            # Find the most recent pending approval
            if self.pending_fallback_approvals:
                task_id = list(self.pending_fallback_approvals.keys())[-1]
                self.pending_fallback_approvals[task_id]['approved'] = approval
                
                # Send confirmation
                status = "✅ approved" if approval else "❌ denied"
                await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=f"{status.capitalize()} 5th account fallback for {task_id}",
                    parse_mode='Markdown'
                )
                
                logger.info(f"📱 User {status} 5th account fallback for {task_id}")
                
        except Exception as e:
            logger.error(f"Error handling fallback response: {e}")
    
    async def submit_comment_link(self, comment_url: str, job_data: dict) -> bool:
        """Submit the comment link to the Telegram group as a reply to the original job post"""
        try:
            if not self.app:
                logger.error("Telegram app not initialized")
                return False
            
            # Just send the comment link without any formatting
            message = comment_url
            
            # Get the original message ID to reply to
            original_message_id = job_data.get('message_id')
            
            if original_message_id:
                # Send as a reply to the original job post
                await self.app.bot.send_message(
                    chat_id=int(config.telegram_main_group_id),
                    text=message,
                    reply_to_message_id=original_message_id
                )
                logger.info(f"Successfully submitted comment link as reply to message {original_message_id}")
            else:
                # Fallback: send without reply if no message ID
                await self.app.bot.send_message(
                    chat_id=int(config.telegram_main_group_id),
                    text=message
                )
                logger.info("Successfully submitted comment link (no reply)")
            
            task_id = job_data.get('task_id', 'Unknown Task')
            log_job_activity(f"Submitted comment link for {task_id}", {"comment_url": comment_url})
            
            return True
            
        except Exception as e:
            logger.error(f"Error submitting comment link: {e}")
            return False
    
    async def send_error_notification(self, error_message: str, job_data: dict = None) -> bool:
        """Send error notification to the notification group"""
        try:
            if not self.app:
                logger.error("Telegram app not initialized")
                return False
            
            task_id = job_data.get('task_id', 'Unknown Task') if job_data else 'Unknown Task'
            
            message = f"❌ Error in Task: {task_id}\\n\\n{error_message}"
            
            # Send to notification group
            result = await self.app.bot.send_message(
                chat_id=int(config.telegram_notification_group_id),
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Sent error notification for {task_id} to group {config.telegram_notification_group_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
            # Try without markdown formatting as fallback
            try:
                await self.app.bot.send_message(
                    chat_id=int(config.telegram_notification_group_id),
                    text=f"Error in Task: {task_id}\\n\\n{error_message}"
                )
                logger.info("Sent error notification without markdown formatting")
                return True
            except Exception as e2:
                logger.error(f"Failed to send error notification even without formatting: {e2}")
                return False

    async def request_comment_selection(self, comment_options: List[str], job_data: dict, tweet_url: str, tweet_text: str = "", account_used: str = "") -> str:
        """
        Send comment options to notification group with inline buttons for selection
        Returns: selected comment
        """
        try:
            if not self.app:
                logger.error("Telegram app not initialized")
                return comment_options[0]  # Return first as fallback
            
            task_id = job_data.get('task_id', 'Unknown')
            
            # Format the options message using HTML for better parsing
            options_message = f"🎯 <b>Comment Selection for {task_id}</b>\n\n"
            
            # Add the actual tweet content so user can see what they're replying to
            if tweet_text:
                # Truncate tweet if it's too long and escape HTML characters
                display_tweet = tweet_text[:300] + "..." if len(tweet_text) > 300 else tweet_text
                # Escape HTML characters to prevent parsing errors
                display_tweet = display_tweet.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                options_message += f"<b>Original Tweet:</b>\n<code>{display_tweet}</code>\n\n"
            
            # Add account used information
            if account_used:
                options_message += f"<b>Tweet read using:</b> {account_used}\n\n"
            
            options_message += f"<b>Tweet URL:</b> {tweet_url}\n\n"
            options_message += f"<b>Choose your reply by clicking a button:</b>\n\n"
            
            for i, comment in enumerate(comment_options, 1):
                # Escape HTML characters in comments
                escaped_comment = comment.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                options_message += f"<b>{i}.</b> <code>{escaped_comment}</code>\n\n"
            
            options_message += f"<b>Click a button above OR reply with number 1-5</b>\n"
            options_message += f"⏰ Timeout: {config.comment_selection_timeout_minutes} minutes"
            
            # Create inline keyboard with buttons
            keyboard = []
            for i, comment in enumerate(comment_options):
                # Truncate button text to 50 chars for display
                button_text = f"{i+1}. {comment[:47]}..." if len(comment) > 50 else f"{i+1}. {comment}"
                # Use callback data to identify selection
                callback_data = f"select_{task_id}_{i}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Store pending selection
            self.pending_selections[task_id] = {
                'comments': comment_options,
                'start_time': time.time(),
                'timeout_minutes': config.comment_selection_timeout_minutes,
                'completed': False,
                'selected_option': None
            }
            
            # Send options to notification group using HTML parsing with buttons
            message = await self.app.bot.send_message(
                chat_id=int(config.telegram_notification_group_id),
                text=options_message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
            logger.info(f"Sent comment selection request for {task_id} to notification group")
            
            # Wait for user response with timeout
            timeout_seconds = config.comment_selection_timeout_minutes * 60
            start_time = time.time()
            
            while time.time() - start_time < timeout_seconds:
                # Check if user has responded via button
                selection_data = self.pending_selections.get(task_id)
                if selection_data and selection_data.get('completed', False):
                    selected_option = selection_data.get('selected_option')
                    if selected_option is not None and 0 <= selected_option < len(comment_options):
                        selected_comment = comment_options[selected_option]
                        logger.info(f"User selected option {selected_option + 1} for {task_id}: {selected_comment[:50]}...")
                        
                        # Clean up
                        del self.pending_selections[task_id]
                        return selected_comment
                
                # Wait a bit before checking again
                await asyncio.sleep(2)
            
            # Timeout reached - select random comment
            selected_comment = random.choice(comment_options)
            selected_index = comment_options.index(selected_comment) + 1
            
            logger.info(f"Timeout reached for {task_id}, randomly selected option {selected_index}: {selected_comment[:50]}...")
            
            # Send timeout notification with button removal
            escaped_comment = selected_comment.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            timeout_message = f"⏰ <b>Timeout for {task_id}</b>\n\n"
            timeout_message += f"No button clicked within {config.comment_selection_timeout_minutes} minutes.\n"
            timeout_message += f"Randomly selected Option {selected_index}:\n<code>{escaped_comment}</code>"
            
            await self.app.bot.send_message(
                chat_id=int(config.telegram_notification_group_id),
                text=timeout_message,
                parse_mode='HTML'
            )
            
            # Clean up
            if task_id in self.pending_selections:
                del self.pending_selections[task_id]
            
            return selected_comment
            
        except Exception as e:
            logger.error(f"Error requesting comment selection: {e}")
            return comment_options[0]  # Return first as fallback


class ReportGenerator:
    """Generates and sends comprehensive reports"""
    
    def __init__(self):
        self.app = None
        # Don't initialize app in __init__, do it async later
    
    async def initialize(self):
        """Initialize the Telegram application asynchronously"""
        if self.app is None:
            await self._initialize_app()
    
    async def _initialize_app(self):
        """Initialize the Telegram application"""
        try:
            from telegram.ext import ApplicationBuilder
            
            builder = ApplicationBuilder()
            builder.token(config.telegram_bot_token)
            self.app = builder.build()
            logger.info("Report generator initialized")
        except Exception as e:
            logger.error(f"Error initializing report generator: {e}")
            raise
    
    async def send_completion_report(self, report_data: dict) -> bool:
        """Send a comprehensive completion report"""
        try:
            if not self.app:
                logger.error("Telegram app not initialized")
                return False
            
            report = self._format_completion_report(report_data)
            
            # Send to notification group
            result = await self.app.bot.send_message(
                chat_id=int(config.telegram_notification_group_id),
                text=report,
                parse_mode='Markdown'
            )
            
            logger.info(f"Sent completion report for {report_data.get('task_id', 'Unknown')} to group {config.telegram_notification_group_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending completion report: {e}")
            # Try without markdown formatting as fallback
            try:
                report_plain = self._format_completion_report_plain(report_data)
                await self.app.bot.send_message(
                    chat_id=int(config.telegram_notification_group_id),
                    text=report_plain
                )
                logger.info("Sent completion report without markdown formatting")
                return True
            except Exception as e2:
                logger.error(f"Failed to send completion report even without formatting: {e2}")
                return False
    
    def _format_completion_report(self, data: dict) -> str:
        """Format the completion report"""
        task_id = data.get('task_id', 'Unknown Task')
        
        report = f"""
📊 **Task Completion Report**

**1. Job ID:** {task_id}

**2. Twitter Post Content:**
{data.get('tweet_content', 'N/A')[:200]}{'...' if len(data.get('tweet_content', '')) > 200 else ''}

**3. Your Reply:**
{data.get('selected_comment', 'N/A')}

**4. Alternative Comments Generated:**
• {data.get('unused_comments', ['N/A', 'N/A'])[0]}
• {data.get('unused_comments', ['N/A', 'N/A'])[1] if len(data.get('unused_comments', [])) > 1 else 'N/A'}

**5. Twitter API Usage:**
{self._format_api_usage(data.get('api_usage', {}))}

**6. Errors/Issues:**
{data.get('errors', 'None reported')}

**7. Comment URL:**
{data.get('comment_url', 'N/A')}

**8. Processing Time:**
{data.get('processing_time', 'N/A')}

**9. Status:**
{'✅ Completed Successfully' if data.get('success', False) else '❌ Completed with Issues'}

---
*Report generated at {data.get('timestamp', 'Unknown time')}*
"""
        return report
    
    def _format_completion_report_plain(self, data: dict) -> str:
        """Format the completion report without markdown"""
        task_id = data.get('task_id', 'Unknown Task')
        
        report = f"""📊 Task Completion Report

1. Job ID: {task_id}

2. Twitter Post Content:
{data.get('tweet_content', 'N/A')[:200]}{'...' if len(data.get('tweet_content', '')) > 200 else ''}

3. Your Reply:
{data.get('selected_comment', 'N/A')}

4. Alternative Comments Generated:
• {data.get('unused_comments', ['N/A', 'N/A'])[0]}
• {data.get('unused_comments', ['N/A', 'N/A'])[1] if len(data.get('unused_comments', [])) > 1 else 'N/A'}

5. Twitter API Usage:
{self._format_api_usage(data.get('api_usage', {}))}

6. Errors/Issues:
{', '.join(data.get('errors', [])) if data.get('errors') else 'None reported'}

7. Comment URL:
{data.get('comment_url', 'N/A')}

8. Processing Time:
{data.get('processing_time', 'N/A')}

9. Status:
{'✅ Completed Successfully' if data.get('success', False) else '❌ Completed with Issues'}

Report generated at {data.get('timestamp', 'Unknown time')}"""
        return report
    
    def _format_api_usage(self, usage_data: dict) -> str:
        """Format API usage information"""
        if not usage_data:
            return "No usage data available"
        
        usage_lines = []
        for client, stats in usage_data.items():
            usage_lines.append(f"• {client}: {stats.get('reads', 0)} reads, {stats.get('writes', 0)} writes")
        
        return "\\n".join(usage_lines) if usage_lines else "No usage data available"


# Factory functions
def create_telegram_monitor(job_callback: Callable[[str, dict], None]) -> TelegramMonitor:
    """Create and return a Telegram monitor instance"""
    return TelegramMonitor(job_callback)


def create_telegram_responder() -> TelegramResponder:
    """Create and return a Telegram responder instance"""
    return TelegramResponder()


def create_report_generator() -> ReportGenerator:
    """Create and return a report generator instance"""
    return ReportGenerator()
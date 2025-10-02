import asyncio
from typing import Dict, List, Optional
from groq import Groq
from loguru import logger
from .config import config
from .utils import TextUtils, RetryHelper


class AIValidator:
    """AI service for validating Twitter jobs and generating comments using Groq"""
    
    def __init__(self):
        self.client = Groq(api_key=config.ai_api_key)
        self.model = config.ai_model
        self.fallback_models = [
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile", 
            "openai/gpt-oss-20b"
        ]
        logger.info(f"AI Validator initialized with model: {self.model}")
    
    async def is_valid_twitter_job(self, message_text: str) -> tuple[bool, str]:
        """
        Validate if a message is a valid Twitter job
        Returns: (is_valid, reason)
        """
        try:
            prompt = self._build_validation_prompt(message_text)
            
            response = await self._make_groq_request(prompt)
            
            # Parse response
            result = response.strip().lower()
            
            if result.startswith("valid"):
                return True, "Valid Twitter job detected"
            elif result.startswith("invalid"):
                reason = result.replace("invalid", "").strip(" :-")
                return False, f"Invalid job: {reason}"
            else:
                # Fallback parsing
                is_valid = "valid" in result and "twitter" in result
                reason = "AI validation uncertain" if not is_valid else "Valid Twitter job"
                return is_valid, reason
                
        except Exception as e:
            logger.error(f"Error validating Twitter job: {e}")
            return False, f"Validation error: {str(e)}"
    
    async def generate_comments(self, tweet_text: str, job_context: str = "") -> List[str]:
        """
        Generate 5 alternative comments for a Twitter post
        Returns: List of 5 comment strings
        """
        try:
            prompt = self._build_comment_prompt(tweet_text, job_context)
            
            response = await self._make_groq_request(prompt)
            
            # Parse the response to extract 5 comments
            comments = self._parse_comments_response(response)
            
            if len(comments) < 5:
                logger.warning(f"Only generated {len(comments)} comments, expected 5")
                # Generate additional comments if needed
                while len(comments) < 5:
                    additional_prompt = self._build_additional_comment_prompt(tweet_text, comments)
                    additional_response = await self._make_groq_request(additional_prompt)
                    new_comments = self._parse_comments_response(additional_response)
                    comments.extend(new_comments)
                    if len(comments) >= 5:
                        break
            
            return comments[:5]  # Return exactly 5 comments
            
        except Exception as e:
            logger.error(f"Error generating comments: {e}")
            # Return fallback comments
            return [
                "Great content! 👍",
                "Thanks for sharing this! 🔥",
                "Interesting perspective!",
                "This is valuable insight 💯",
                "Really helpful, appreciate it!"
            ]
    
    async def generate_comment(self, prompt: str) -> Optional[str]:
        """Generate a single realistic comment using AI"""
        try:
            response = await self._make_groq_request(prompt)
            
            if response and len(response.strip()) > 0:
                # Clean the response
                comment = response.strip()
                # Remove any quotes or extra formatting
                comment = comment.strip('"\'`')
                
                return comment
            else:
                logger.error("AI returned empty response")
                return None
                
        except Exception as e:
            logger.error(f"Error generating single comment: {e}")
            return None
    
    def _build_validation_prompt(self, message_text: str) -> str:
        """Build prompt for Twitter job validation"""
        return f"""
You are a Twitter job validator. Analyze the following message and determine if it's a VALID TWITTER JOB.

A VALID TWITTER JOB must have ALL of these characteristics:
1. Contains "Twitter" in the title or task type
2. Has a Twitter/X URL (twitter.com or x.com)
3. Has a task number format like "R[number] - REQUIRED TASK NUMBER [ number ]"
4. Asks for engagement (likes, comments, replies, impressions)
5. Is NOT an Instagram job
6. Is NOT a reward distribution announcement
7. Is NOT a general update or notification

INVALID examples include:
- Instagram jobs (even if they have task numbers)
- Reward distribution announcements
- General updates like "Task Ready Guys"
- Non-engagement tasks

Message to analyze:
{message_text}

Respond with ONLY:
"VALID - [brief reason]" OR "INVALID - [brief reason]"

Response:"""
    
    def _build_comment_prompt(self, tweet_text: str, job_context: str = "") -> str:
        """Build prompt for generating comments"""
        clean_tweet = TextUtils.clean_text(tweet_text)
        
        return f"""
Generate 5 different Twitter replies that sound like REAL PEOPLE on X (Twitter). Make them feel completely natural and human.

Tweet content:
{clean_tweet}

IMPORTANT REQUIREMENTS:
- Sound like actual crypto enthusiasts
- Use emojis ONLY 50% of the time, and NOT always at the end
- Keep comments SHORT - 1 sentence is perfect, max 2 sentences
- DON'T use hashtags often - very sparingly
- Some can be questions, some statements, some reactions


Format your response exactly like this:
COMMENT 1: [comment]
COMMENT 2: [comment]
COMMENT 3: [comment]
COMMENT 4: [comment]
COMMENT 5: [comment]

Generate the comments:"""
    
    def _build_additional_comment_prompt(self, tweet_text: str, existing_comments: List[str]) -> str:
        """Build prompt for generating additional comments"""
        clean_tweet = TextUtils.clean_text(tweet_text)
        existing_text = "\n".join([f"- {comment}" for comment in existing_comments])
        
        return f"""
Generate 1 more creative Twitter reply for this tweet. Make it different from the existing comments.

Tweet content:
{clean_tweet}

Existing comments (make yours different):
{existing_text}

Requirements:
1. Must be unique and different from existing comments
2. Keep under 240 characters
3. Be engaging and authentic
4. Include relevant emojis

Format: COMMENT: [your comment]

Generate the comment:"""
    
    async def _make_groq_request(self, prompt: str) -> str:
        """Make request to Groq API with retry logic and model fallback"""
        async def _request_with_model(model_name: str):
            try:
                response = self.client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    model=model_name,
                    temperature=0.7,
                    max_tokens=1000
                )
                return response.choices[0].message.content
            except Exception as e:
                if "model_decommissioned" in str(e) or "invalid_request_error" in str(e):
                    logger.warning(f"Model {model_name} failed: {e}")
                    raise ModelDecommissionedError(f"Model {model_name} is not available")
                raise e
        
        # Try primary model first
        try:
            return await RetryHelper.retry_async(
                lambda: _request_with_model(self.model), 
                max_retries=2
            )
        except ModelDecommissionedError:
            logger.warning(f"Primary model {self.model} failed, trying fallback models...")
            
            # Try fallback models
            for fallback_model in self.fallback_models:
                if fallback_model != self.model:  # Skip if same as primary
                    try:
                        logger.info(f"Trying fallback model: {fallback_model}")
                        result = await RetryHelper.retry_async(
                            lambda: _request_with_model(fallback_model),
                            max_retries=1
                        )
                        logger.info(f"Successfully used fallback model: {fallback_model}")
                        return result
                    except ModelDecommissionedError:
                        logger.warning(f"Fallback model {fallback_model} also failed")
                        continue
                    except Exception as e:
                        logger.warning(f"Error with fallback model {fallback_model}: {e}")
                        continue
            
            # If all models fail, raise the original error
            raise Exception("All available models failed or are decommissioned")
    
    def _parse_comments_response(self, response: str) -> List[str]:
        """Parse comments from AI response"""
        comments = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Look for comment patterns
            if line.startswith('COMMENT'):
                # Extract comment after the colon
                if ':' in line:
                    comment = line.split(':', 1)[1].strip()
                    if comment and len(comment) <= 280:  # Twitter character limit
                        comments.append(comment)
            elif line.startswith(('1.', '2.', '3.', '-')):
                # Handle numbered or bulleted lists
                comment = line.split('.', 1)[-1].split('-', 1)[-1].strip()
                if comment and len(comment) <= 280:
                    comments.append(comment)
        
        # Clean up comments
        cleaned_comments = []
        for comment in comments:
            # Remove quotes if present
            comment = comment.strip('"\'')
            if comment and comment not in cleaned_comments:
                cleaned_comments.append(comment)
        
        return cleaned_comments


class ModelDecommissionedError(Exception):
    """Custom exception for decommissioned models"""
    pass


# Factory function for easy import
def create_ai_validator() -> AIValidator:
    """Create and return an AI validator instance"""
    return AIValidator()
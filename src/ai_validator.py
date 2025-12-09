import asyncio
import os
from typing import Dict, List, Optional
from groq import Groq
from openai import OpenAI
from loguru import logger
from .config import config
from .utils import TextUtils, RetryHelper


class AIValidator:
    """AI service for validating Twitter jobs (Groq) and generating comments (GPT-4o > Groq)"""
    
    def __init__(self):
        # Groq client for validation
        self.groq_client = Groq(api_key=config.ai_api_key)
        # Use llama-3.1-8b-instant as default for better crypto comment generation
        self.model = "llama-3.3-70b-versatile"
        self.fallback_models = [
            "llama-3.1-70b-versatile", 
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]
        
        # GitHub Models client for comment generation (GPT-4o -> Groq fallback)
        github_token = os.environ.get("GITHUB_TOKEN")
        if github_token and github_token.startswith("github_pat_"):
            try:
                self.github_client = OpenAI(
                    base_url="https://models.github.ai/inference",
                    api_key=github_token
                )
                self.github_available = True
                # Model priority: GPT-4o first, then GPT-4o-mini as fallback
                self.github_models = ["openai/gpt-4o", "openai/gpt-4o-mini"]
                logger.info("GitHub Models client initialized (GPT-4o -> Groq fallback)")
            except Exception as e:
                logger.warning(f"GitHub Models client initialization failed: {e}. Using Groq only.")
                self.github_available = False
        else:
            self.github_available = False
            logger.info("No GitHub token configured. Using Groq for comment generation.")
        
        # Track which model was used for the last generation
        self.last_model_used = None
        
        logger.info(f"AI Validator initialized with Groq model: {self.model}")
        if self.github_available:
            logger.info(f"GitHub Models available: {', '.join(self.github_models)}")
    
    def _has_valid_task_format(self, message_text: str) -> tuple[bool, str, str]:
        """
        Check if message has valid task format with Round number and Task number
        Format: R[number] - REQUIRED TASK NUMBER [ number ]
        Returns: (has_format, round_number, task_number)
        """
        import re
        # Pattern to match: R139 - REQUIRED TASK NUMBER [ 24 ]
        pattern = r'R(\d+)\s*[-–]\s*(?:REQUIRED\s+)?TASK\s+(?:NUMBER\s*)?\[\s*(\d+)\s*\]'
        match = re.search(pattern, message_text, re.IGNORECASE)
        
        if match:
            round_num = match.group(1)
            task_num = match.group(2)
            return True, round_num, task_num
        
        return False, "", ""
    
    def _has_twitter_url(self, message_text: str) -> bool:
        """Check if message contains a Twitter/X URL"""
        import re
        pattern = r'https?://(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/\d+'
        return bool(re.search(pattern, message_text, re.IGNORECASE))
    
    async def is_valid_twitter_job(self, message_text: str) -> tuple[bool, str]:
        """
        Validate if a message is a valid Twitter job
        Must have: Round number, Task number, and Twitter URL
        Returns: (is_valid, reason)
        """
        try:
            # STEP 1: Check for proper task format (Round + Task number)
            has_format, round_num, task_num = self._has_valid_task_format(message_text)
            
            if not has_format:
                logger.info("Job rejected: Missing proper task format (R[num] - TASK NUMBER [num])")
                return False, "Missing task format - needs Round number and Task number"
            
            # STEP 2: Check for Twitter/X URL
            if not self._has_twitter_url(message_text):
                logger.info("Job rejected: No Twitter/X URL found")
                return False, "No Twitter URL found in message"
            
            # STEP 3: Check it's not just "like and RT" (no comment needed)
            message_lower = message_text.lower()
            
            # Keywords that indicate comments are needed
            comment_keywords = ['comment', 'reply', 'creative', 'response', 'impression']
            needs_comment = any(keyword in message_lower for keyword in comment_keywords)
            
            # Keywords that indicate ONLY like/RT (no comment)
            like_only_keywords = ['like and rt only', 'like & rt only', 'only like and rt', 'like and retweet only']
            is_like_only = any(keyword in message_lower for keyword in like_only_keywords)
            
            if is_like_only and not needs_comment:
                logger.info(f"Job R{round_num} Task {task_num} rejected: Like/RT only task (no comment needed)")
                return False, f"R{round_num} Task {task_num} - Like/RT only (no comment needed)"
            
            logger.info(f"Valid job format detected: R{round_num} - Task {task_num}")
            return True, f"Valid Twitter job: R{round_num} - Task {task_num}"
                
        except Exception as e:
            logger.error(f"Error validating Twitter job: {e}")
            return False, f"Validation error: {str(e)}"
    
    async def generate_comments(self, tweet_text: str, job_context: str = "") -> tuple[List[str], str]:
        """
        Generate 5 alternative comments for a Twitter post
        Priority: GPT-5 -> GPT-4o -> Groq
        Returns: (List of 5 comment strings, model_used)
        """
        self.last_model_used = None
        
        # Try GitHub Models first (GPT-5 -> GPT-4o)
        if self.github_available:
            for model in self.github_models:
                try:
                    comments = await self._generate_comments_github(tweet_text, job_context, model)
                    if comments and len(comments) >= 5:
                        self.last_model_used = model
                        return comments[:5], model
                except Exception as e:
                    logger.warning(f"{model} failed: {e}, trying next model...")
                    continue
        
        # Fallback to Groq
        try:
            logger.info("Using Groq for comment generation (GitHub Models unavailable)")
            comments = await self._generate_comments_groq(tweet_text, job_context)
            self.last_model_used = f"Groq/{self.model}"
            return comments, f"Groq/{self.model}"
        except Exception as e:
            logger.error(f"All AI models failed: {e}")
            self.last_model_used = "Fallback (no AI)"
            return self._get_fallback_comments(), "Fallback (no AI)"
    
    async def _generate_comments_github(self, tweet_text: str, job_context: str, model: str) -> List[str]:
        """Generate comments using GitHub Models (GPT-4o)"""
        try:
            prompt = self._build_chatgpt_comment_prompt(tweet_text, job_context)
            
            response = self.github_client.chat.completions.create(
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful assistant that generates natural, casual social media comments for cryptocurrency and technology posts. Focus on positive, community-oriented responses."
                    },
                    {"role": "user", "content": prompt}
                ],
                model=model,
                max_tokens=400,
                temperature=0.8
            )
            
            result = response.choices[0].message.content
            logger.info(f"Raw {model} response: {result[:300]}...")
            comments = self._parse_comments_response(result)
            
            if len(comments) < 3:
                # Too few comments parsed - try next model instead of filling with fallbacks
                logger.warning(f"{model} generated only {len(comments)} comments, trying next model...")
                raise Exception(f"Insufficient comments parsed from {model}")
            
            if len(comments) < 5:
                logger.info(f"{model} generated {len(comments)} comments, filling remaining with fallbacks")
                fallbacks = self._get_fallback_comments()
                comments.extend(fallbacks[:5-len(comments)])
            
            logger.info(f"Generated {len(comments)} comments using {model}")
            return comments[:5]
            
        except Exception as e:
            logger.error(f"{model} comment generation failed: {e}")
            raise  # Re-raise to try next model
    
    async def _generate_comments_groq(self, tweet_text: str, job_context: str = "") -> List[str]:
        """Generate comments using Groq (fallback)"""
        try:
            prompt = self._build_comment_prompt(tweet_text, job_context)
            
            response = await self._make_groq_request(prompt)
            logger.info(f"Raw Groq response: {response[:300]}...")
            
            # Parse the response to extract 5 comments
            comments = self._parse_comments_response(response)
            
            if len(comments) < 3:
                logger.warning(f"Groq only generated {len(comments)} comments, using fallbacks")
                return self._get_fallback_comments()
            
            if len(comments) < 5:
                logger.info(f"Groq generated {len(comments)} comments, filling remaining with fallbacks")
                fallbacks = self._get_fallback_comments()
                comments.extend(fallbacks[:5-len(comments)])
            
            logger.info(f"Generated {len(comments)} comments using Groq")
            return comments[:5]  # Return exactly 5 comments
            
        except Exception as e:
            logger.error(f"Groq comment generation failed: {e}")
            return self._get_fallback_comments()
    
    async def generate_comment(self, prompt: str) -> Optional[str]:
        """Generate a single realistic comment using AI (GPT-4o > Groq)"""
        try:
            # Try GitHub Models first
            if self.github_available:
                for model in self.github_models:
                    try:
                        response = self.github_client.chat.completions.create(
                            messages=[
                                {
                                    "role": "system", 
                                    "content": "You are a helpful assistant that generates natural, casual social media comments."
                                },
                                {"role": "user", "content": prompt}
                            ],
                            model=model,
                            max_tokens=100,
                            temperature=0.8
                        )
                        
                        comment = response.choices[0].message.content.strip()
                        comment = comment.strip('"\'`')
                        logger.info(f"Generated single comment using {model}")
                        return comment
                        
                    except Exception as e:
                        logger.warning(f"{model} single comment failed: {e}, trying next...")
                        continue
            
            # Fallback to Groq
            response = await self._make_groq_request(prompt)
            
            if response and len(response.strip()) > 0:
                # Clean the response
                comment = response.strip()
                # Remove any quotes or extra formatting
                comment = comment.strip('"\'`')
                logger.info("Generated single comment using Groq")
                return comment
            else:
                logger.error("AI returned empty response")
                return None
                
        except Exception as e:
            logger.error(f"Error generating single comment: {e}")
            return None
    
    def _build_chatgpt_comment_prompt(self, tweet_text: str, job_context: str = "") -> str:
        """Build optimized prompt for ChatGPT comment generation"""
        clean_tweet = TextUtils.clean_text(tweet_text)
        
        return f"""Generate 5 Twitter replies for this crypto tweet. Be a real person, not a bot.

LENGTH MIX (IMPORTANT):
- 2 comments: SHORT (3-6 words) - punchy reactions
- 3 comments: MEDIUM (7-12 words) - more substance but still casual

STYLE RULES:
- Use slang like "ngl", "fr", "tbh" RARELY (max 1 out of 5)
- NEVER use "lowkey" - it's overused
- NEVER use hyphens/dashes
- EMOJI: Only 1-2 comments max can have emoji (most should have NONE)
- Start most comments with LOWERCASE (looks more casual/human)
- Each comment references the tweet
- Natural speech: "yo", "bro", "damn", "wait", "wild", "sick", "lets go"
- Mix vibes: curious, hyped, impressed, funny

BANNED: "solid", "great content", "nice", "interesting", "lowkey", "let's gooo"

Tweet: {clean_tweet}

Write 5 comments (2 short, 3 medium):
1. 
2. 
3. 
4. 
5. """
    
    def _get_fallback_comments(self) -> List[str]:
        """Return varied fallback comments - mix of short and medium, few emojis, lowercase starts"""
        fallback_sets = [
            [
                "yo this is huge",
                "been waiting for something like this to drop",
                "finally",
                "my portfolio definitely likes this one 🔥",
                "not sleeping on this opportunity"
            ],
            [
                "the move we needed",
                "this is exactly what the community been asking for",
                "bookmarked",
                "team really coming through with this one",
                "bullish on this 🚀"
            ],
            [
                "bro this is it",
                "cant believe they actually pulled this off",
                "say less im in",
                "this hittin different than usual",
                "mad respect 💪"
            ],
            [
                "yooo they delivered",
                "this could be bigger than people realize",
                "we move",
                "love to see them keep pushing forward",
                "bullish 📈"
            ]
        ]
        
        import random
        return random.choice(fallback_sets)
    
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
        """Build prompt for generating comments (Groq fallback)"""
        clean_tweet = TextUtils.clean_text(tweet_text)
        
        return f"""Generate 5 Twitter replies for this crypto tweet. Mix of short and medium length.

LENGTH PATTERN:
- Comment 1: SHORT (3-6 words)
- Comment 2: MEDIUM (7-12 words)  
- Comment 3: SHORT (3-6 words)
- Comment 4: MEDIUM (7-12 words)
- Comment 5: MEDIUM (7-12 words)

Tweet: {clean_tweet}

RULES:
- Use "ngl", "fr", "tbh" RARELY (max 1 out of 5)
- NEVER use "lowkey" or hyphens
- EMOJI: Only 1-2 comments can have emoji (3-4 should have NO emoji)
- Start most comments with lowercase (not every word capitalized)
- Reference the tweet content
- Casual: "yo", "bro", "damn", "wait", "wild", "sick", "lets go"
- Mix vibes: hyped, curious, impressed, funny

BANNED: "solid", "great content", "nice", "interesting", "lowkey"

Output (clean text only):
COMMENT 1: [short]
COMMENT 2: [medium]
COMMENT 3: [short] 
COMMENT 4: [medium]
COMMENT 5: [medium]"""
    
    def _build_additional_comment_prompt(self, tweet_text: str, existing_comments: List[str]) -> str:
        """Build prompt for generating additional comments"""
        clean_tweet = TextUtils.clean_text(tweet_text)
        existing_text = "\n".join([f"- {comment}" for comment in existing_comments])
        
        return f"""
Generate 1 more authentic Twitter reply for this tweet. Make it completely different from existing comments.

Tweet: {clean_tweet}

Existing comments (make yours unique):
{existing_text}

Rules:
- Must be completely different from existing comments
- Use "ngl", "fr", "tbh" SPARINGLY (only if existing comments don't have them)
- NEVER use "lowkey" or hyphens
- Vary length: short (4-7 words) or medium (8-14 words)
- Only use emoji if natural (30% chance)
- Sound like a real person, casual grammar
- Reference something specific from the tweet

Format: COMMENT: [your unique comment]

Generate:"""
    
    async def _make_groq_request(self, prompt: str) -> str:
        """Make request to Groq API with retry logic and model fallback"""
        async def _request_with_model(model_name: str):
            try:
                response = self.groq_client.chat.completions.create(
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
        """Parse comments from AI response - flexible format handling"""
        comments = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            comment = None
            
            # Pattern 1: "COMMENT 1: text" or "COMMENT: text"
            if line.upper().startswith('COMMENT'):
                if ':' in line:
                    comment = line.split(':', 1)[1].strip()
            
            # Pattern 2: "1. text" or "1) text" or "1 text"
            elif line[0].isdigit():
                import re
                match = re.match(r'^\d+[\.\)\s]\s*(.+)$', line)
                if match:
                    comment = match.group(1).strip()
            
            # Pattern 3: "- text" or "* text"
            elif line.startswith(('-', '*', '•')):
                comment = line[1:].strip()
            
            # Pattern 4: Just a plain line that looks like a comment (no special prefix)
            elif len(line) > 5 and len(line) <= 280 and not line.startswith(('#', '@', 'http')):
                # If it's a reasonable length and not a hashtag/mention/url, treat as comment
                comment = line
            
            # Validate and add comment
            if comment and len(comment) > 3 and len(comment) <= 280:
                # Remove quotes if wrapped
                comment = comment.strip('"\'`')
                if comment and comment not in comments:
                    comments.append(comment)
        
        # Clean up comments
        cleaned_comments = []
        for comment in comments:
            import re
            # Remove word count annotations
            comment = re.sub(r'\s*[\(\[\-]\s*\d+\s*words?\s*[\)\]]*\s*$', '', comment, flags=re.IGNORECASE)
            comment = re.sub(r'\s*\(\d+ words\)\s*$', '', comment)
            comment = comment.strip()
            
            if comment and comment not in cleaned_comments:
                cleaned_comments.append(comment)
        
        return cleaned_comments[:5]  # Return max 5
    
    def _validate_and_fix_pattern(self, comments: List[str]) -> List[str]:
        """Validate and fix the Medium-Short-Medium-Short-Medium pattern"""
        expected_pattern = ["MEDIUM", "SHORT", "MEDIUM", "SHORT", "MEDIUM"]
        fixed_comments = []
        
        for i, comment in enumerate(comments):
            word_count = len(comment.split())
            expected = expected_pattern[i]
            
            # Check if word count matches expected pattern
            if expected == "SHORT" and 3 <= word_count <= 8:
                # Perfect short comment
                fixed_comments.append(comment)
            elif expected == "MEDIUM" and 9 <= word_count <= 15:
                # Perfect medium comment
                fixed_comments.append(comment)
            elif expected == "SHORT" and word_count < 3:
                # Too short for SHORT position - extend it
                extended_comment = self._extend_short_comment(comment)
                fixed_comments.append(extended_comment)
                logger.warning(f"Extended too-short comment at position {i+1}: '{comment}' -> '{extended_comment}'")
            elif expected == "SHORT" and word_count > 8:
                # Too long for SHORT position - shorten it
                shortened_comment = self._shorten_comment(comment, target_max=8)
                fixed_comments.append(shortened_comment)
                logger.warning(f"Shortened too-long comment at position {i+1}: '{comment}' -> '{shortened_comment}'")
            elif expected == "MEDIUM" and word_count < 9:
                # Too short for MEDIUM position - extend it
                extended_comment = self._extend_medium_comment(comment)
                fixed_comments.append(extended_comment)
                logger.warning(f"Extended too-short medium comment at position {i+1}: '{comment}' -> '{extended_comment}'")
            elif expected == "MEDIUM" and word_count > 15:
                # Too long for MEDIUM position - shorten it
                shortened_comment = self._shorten_comment(comment, target_max=15)
                fixed_comments.append(shortened_comment)
                logger.warning(f"Shortened too-long medium comment at position {i+1}: '{comment}' -> '{shortened_comment}'")
            else:
                # Use as-is if close enough
                fixed_comments.append(comment)
        
        return fixed_comments
    
    def _extend_short_comment(self, comment: str) -> str:
        """Extend a too-short comment to make it proper SHORT (3-8 words)"""
        extensions = [" fr", " honestly", " ngl", " for sure", " tbh"]
        extended = comment + extensions[0]  # Add the first extension
        return extended if len(extended.split()) >= 3 else comment + " for real"
    
    def _extend_medium_comment(self, comment: str) -> str:
        """Extend a too-short comment to make it proper MEDIUM (9-15 words)"""
        if "this" in comment.lower():
            return comment + ", definitely worth checking out honestly"
        elif "good" in comment.lower():
            return comment + " and definitely worth keeping an eye on"
        elif "solid" in comment.lower():
            return comment + ", really appreciate shares like this from the community"
        else:
            return comment + ", this could be something worth watching closely"
    
    def _shorten_comment(self, comment: str, target_max: int) -> str:
        """Shorten a comment to fit target word count"""
        words = comment.split()
        if len(words) <= target_max:
            return comment
        
        # Try to keep the most important words
        shortened = " ".join(words[:target_max])
        
        # Clean up if it ends awkwardly
        if shortened.endswith(("a", "the", "this", "that", "and", "or", "but")):
            shortened = " ".join(words[:target_max-1])
        
        return shortened


class ModelDecommissionedError(Exception):
    """Custom exception for decommissioned models"""
    pass


# Factory function for easy import
def create_ai_validator() -> AIValidator:
    """Create and return an AI validator instance"""
    return AIValidator()

import asyncio
import os
from typing import Dict, List, Optional
from groq import Groq
from openai import OpenAI
from loguru import logger
from .config import config
from .utils import TextUtils, RetryHelper


class AIValidator:
    """AI service for validating Twitter jobs (Groq) and generating comments (ChatGPT)"""
    
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
        
        # ChatGPT client for comment generation
        try:
            self.chatgpt_client = OpenAI(
                base_url="https://models.github.ai/inference",
                api_key=os.environ.get("GITHUB_TOKEN")
            )
            self.chatgpt_model = "openai/gpt-4o"
            self.chatgpt_available = True
            logger.info("ChatGPT client initialized for comment generation")
        except Exception as e:
            logger.warning(f"ChatGPT client initialization failed: {e}. Falling back to Groq for comments.")
            self.chatgpt_available = False
        
        logger.info(f"AI Validator initialized with Groq model: {self.model}")
        if self.chatgpt_available:
            logger.info(f"ChatGPT model available: {self.chatgpt_model}")
    
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
        Generate 5 alternative comments for a Twitter post using ChatGPT (preferred) or Groq (fallback)
        Returns: List of 5 comment strings
        """
        try:
            # Try ChatGPT first
            if self.chatgpt_available:
                return await self._generate_comments_chatgpt(tweet_text, job_context)
            else:
                # Fallback to Groq
                logger.info("Using Groq for comment generation (ChatGPT unavailable)")
                return await self._generate_comments_groq(tweet_text, job_context)
                
        except Exception as e:
            logger.error(f"Error generating comments: {e}")
            # Return fallback comments
            return [
                "this looks interesting 👀",
                "good stuff here",
                "thanks for sharing this",
                "solid content fr",
                "always appreciate these updates"
            ]
    
    async def _generate_comments_chatgpt(self, tweet_text: str, job_context: str = "") -> List[str]:
        """Generate comments using ChatGPT"""
        try:
            prompt = self._build_chatgpt_comment_prompt(tweet_text, job_context)
            
            response = self.chatgpt_client.chat.completions.create(
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful assistant that generates natural, casual social media comments for cryptocurrency and technology posts. Focus on positive, community-oriented responses."
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.chatgpt_model,
                max_tokens=400,
                temperature=0.7
            )
            
            result = response.choices[0].message.content
            comments = self._parse_comments_response(result)
            
            if len(comments) < 5:
                logger.warning(f"ChatGPT generated only {len(comments)} comments, padding with fallbacks")
                # Add fallback comments to reach 5
                fallbacks = self._get_fallback_comments()
                comments.extend(fallbacks[:5-len(comments)])
            
            logger.info(f"Generated {len(comments)} comments using ChatGPT")
            return comments[:5]
            
        except Exception as e:
            logger.error(f"ChatGPT comment generation failed: {e}")
            # Fallback to Groq
            return await self._generate_comments_groq(tweet_text, job_context)
    
    async def _generate_comments_groq(self, tweet_text: str, job_context: str = "") -> List[str]:
        """Generate comments using Groq (fallback)"""
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
            
            logger.info(f"Generated {len(comments)} comments using Groq")
            return comments[:5]  # Return exactly 5 comments
            
        except Exception as e:
            logger.error(f"Groq comment generation failed: {e}")
            return self._get_fallback_comments()
    
    async def generate_comment(self, prompt: str) -> Optional[str]:
        """Generate a single realistic comment using AI (ChatGPT preferred, Groq fallback)"""
        try:
            if self.chatgpt_available:
                try:
                    response = self.chatgpt_client.chat.completions.create(
                        messages=[
                            {
                                "role": "system", 
                                "content": "You are a helpful assistant that generates natural, casual social media comments."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        model=self.chatgpt_model,
                        max_tokens=100,
                        temperature=0.7
                    )
                    
                    comment = response.choices[0].message.content.strip()
                    comment = comment.strip('"\'`')
                    logger.info("Generated single comment using ChatGPT")
                    return comment
                    
                except Exception as e:
                    logger.warning(f"ChatGPT single comment failed: {e}, falling back to Groq")
            
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
        
        return f"""Generate 5 authentic crypto community comments following this STRICT pattern:

POSITION 1: MEDIUM comment (MUST be 9-15 words)
POSITION 2: SHORT comment (MUST be 3-8 words)
POSITION 3: MEDIUM comment (MUST be 9-15 words)
POSITION 4: SHORT comment (MUST be 3-8 words)
POSITION 5: MEDIUM comment (MUST be 9-15 words)

EXAMPLES WITH WORD COUNTS:

SHORT COMMENTS (3-8 words exactly):
- "game changer fr 🚀" ✅ PERFECT
- "this looks promising 👀" ✅ PERFECT
- "big moves happening here" ✅ PERFECT
- "already set my reminder 🔔" ✅ PERFECT

MEDIUM COMMENTS (9-15 words exactly):
- "officials talking crypto? that's actually pretty interesting to see 🤔" ✅ PERFECT
- "gonna read the docs first though, looks really promising" ✅ PERFECT
- "yield farming space getting crowded but innovation is still good 💪" ✅ PERFECT

CRITICAL RULES:
- COUNT WORDS CAREFULLY before generating each comment
- SHORT = exactly 3-8 words (no less, no more)
- MEDIUM = exactly 9-15 words (no less, no more)
- NO word count numbers in the actual comments
- Use emojis in 4 out of 5 comments (80% emoji usage)
- Place emojis naturally: at end, middle, or relevant context
- Use crypto/finance relevant emojis: 🚀 💎 🔥 👀 💯 📈 💰 ⚡ 🌙 🎯 🔔 💪 🤔
- Natural contractions and lowercase style

Post to comment on: {clean_tweet}

Generate 5 clean comments (include emojis in 4 out of 5):
COMMENT 1: [MEDIUM comment - clean text only]
COMMENT 2: [SHORT comment - clean text only] 
COMMENT 3: [MEDIUM comment - clean text only]
COMMENT 4: [SHORT comment - clean text only]
COMMENT 5: [MEDIUM comment - clean text only]"""
    
    def _get_fallback_comments(self) -> List[str]:
        """Return varied fallback comments with Medium-Short-Medium-Short-Medium pattern and 4/5 emojis"""
        fallback_sets = [
            # Set 1: Following the new pattern with 4/5 emojis
            [
                "this looks pretty interesting worth checking out 🚀",  # medium
                "good stuff here 👀",       # short  
                "definitely gonna keep an eye on this development 💪",    # medium
                "solid content fr",  # short (no emoji)
                "always appreciate updates like this from the community 💯"  # medium
            ],
            # Set 2: Different variety with 4/5 emojis
            [
                "this could be something big happening in the space 📈",     # medium
                "gonna check this 🔥",      # short
                "appreciate the share and keeping us all updated",  # medium (no emoji)
                "worth watching 🎯",  # short
                "good to see progress like this honestly ngl 🌙"  # medium
            ],
            # Set 3: Natural crypto style with 4/5 emojis
            [
                "interesting take on what's happening in the market 🤔",           # medium
                "solid post",    # short (no emoji)
                "this could definitely be something worth watching closely 👀",     # medium
                "looks promising 💎",  # short
                "always good when we see moves like this ⚡"  # medium
            ]
        ]
        
        # Randomly select one set to avoid repetition
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
        
        return f"""Generate 5 authentic human-like crypto community comments following STRICT word count pattern:

POSITION 1: MEDIUM comment (MUST be exactly 9-15 words)
POSITION 2: SHORT comment (MUST be exactly 3-8 words)
POSITION 3: MEDIUM comment (MUST be exactly 9-15 words)
POSITION 4: SHORT comment (MUST be exactly 3-8 words)
POSITION 5: MEDIUM comment (MUST be exactly 9-15 words)

Tweet content: {clean_tweet}

CRITICAL WORD COUNT RULES:
- SHORT = 3-8 words (never less than 3, never more than 8)
- MEDIUM = 9-15 words (never less than 9, never more than 15)
- Count every single word before generating
- DO NOT include word counts in the actual comments
- Just provide clean comment text

REQUIREMENTS: 
- Sound like actual crypto enthusiasts with genuine reactions
- COUNT WORDS CAREFULLY - this is critical
- Use emojis in 4 out of 5 comments (80% emoji usage)
- Crypto/finance emojis: 🚀 💎 🔥 👀 💯 📈 💰 ⚡ 🌙 🎯 🔔 💪 🤔
- Place emojis naturally in context
- Casual grammar: lowercase, contractions (gonna, can't, tbh)
- Varied tones: excited, curious, neutral
- Crypto slang sparingly: "fr", "ngl", "imo" in max 1 comment
- Make each comment unique and human

Format - provide ONLY clean comment text:
COMMENT 1: [medium comment text only]
COMMENT 2: [short comment text only]
COMMENT 3: [medium comment text only] 
COMMENT 4: [short comment text only]
COMMENT 5: [medium comment text only]"""
    
    def _build_additional_comment_prompt(self, tweet_text: str, existing_comments: List[str]) -> str:
        """Build prompt for generating additional comments"""
        clean_tweet = TextUtils.clean_text(tweet_text)
        existing_text = "\n".join([f"- {comment}" for comment in existing_comments])
        
        return f"""
Generate 1 more authentic human-like Twitter reply for this tweet. Make it completely different from existing comments.

Tweet content:
{clean_tweet}

Existing comments (make yours unique):
{existing_text}

Requirements:
1. Must be completely different from existing comments in tone and content
2. Use natural human speech patterns and casual grammar
3. Vary the length: could be short (3-6 words) or medium (10-20 words)
4. Only use emoji if it feels natural (30% chance)
5. Sound like a real person with genuine reaction
6. Use lowercase, contractions, natural flow
7. Could be question, observation, personal reaction, or related thought

Format: COMMENT: [your unique comment]

Generate the comment:"""
    
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
        """Parse comments from AI response and validate word count pattern"""
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
            
            # CRITICAL: Remove any word count validation text that might have leaked in
            # Remove patterns like " (12 words)", " - 12 words", etc.
            import re
            comment = re.sub(r'\s*[\(\[\-]\s*\d+\s*words?\s*[\)\]]*\s*$', '', comment, flags=re.IGNORECASE)
            comment = re.sub(r'\s*[\(\[\-]\s*word count:?\s*\d+\s*[\)\]]*\s*$', '', comment, flags=re.IGNORECASE)
            comment = re.sub(r'\s*[\(\[\-]\s*\d+\s*w\s*[\)\]]*\s*$', '', comment, flags=re.IGNORECASE)
            
            # Remove any trailing validation text
            comment = re.sub(r'\s*" \(\d+ words\)\s*$', '', comment)
            comment = re.sub(r'\s*\(\d+ words\)\s*$', '', comment)
            
            # Final cleanup
            comment = comment.strip()
            
            if comment and comment not in cleaned_comments:
                cleaned_comments.append(comment)
        
        # Validate and fix word count pattern if we have exactly 5 comments
        if len(cleaned_comments) == 5:
            cleaned_comments = self._validate_and_fix_pattern(cleaned_comments)
        
        return cleaned_comments
    
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

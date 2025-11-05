#!/usr/bin/env python3
"""
Simple AI Prompt Checker for Twitter Comments
Test your AI prompt with different models and tweets
"""

import os
from dotenv import load_dotenv
from groq import Groq
from loguru import logger

# Load environment variables
load_dotenv()

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=''), format="<green>{time:HH:mm:ss}</green> | {message}")

class SimpleAIChecker:
    """Simple AI prompt tester"""
    
    def __init__(self):
        # Default AI model
        self.current_model = "llama-3.3-70b-versatile"
        
        # Available models
        self.models = [
            "llama-3.1-8b-instant",
            "llama-3.1-70b-versatile", 
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]
        
        # Your test prompt
        self.prompt = """Generate 5 Twitter replies that sound like REAL cryptolover on Twitter. 
Make them feel completely natural and human.

Tweet content:
{tweet_text}

IMPORTANT REQUIREMENTS:
- Sound like actual crypto enthusiasts
- Use emojis ONLY 50% of the time, and NOT always at the end
- Keep comments SHORT - 1 short sentence is perfect. 80% short 15% medium 5% long
- be casual
- DON'T use hashtags often - very sparingly
- Some can be questions, some statements, some reactions

Format your response exactly like this:
COMMENT 1: [comment]
COMMENT 2: [comment]
COMMENT 3: [comment]
COMMENT 4: [comment]
COMMENT 5: [comment]"""

        # Default test tweet
        self.test_tweet = """LATEST🚨 

The White House says President Trump has "officially ended the 
Biden administration's war on the cryptocurrency industry."🇺🇸

"""
        
        # Initialize AI client
        try:
            api_key = os.getenv('AI_API_KEY')
            self.ai_client = Groq(api_key=api_key)
            logger.success(f"✅ AI client ready with {self.current_model}")
        except Exception as e:
            logger.error(f"❌ AI setup failed: {e}")
            self.ai_client = None
    
    def generate_comments(self, tweet_text=None):
        """Generate comments for the tweet"""
        if not self.ai_client:
            logger.error("❌ AI client not available")
            return []
        
        if tweet_text is None:
            tweet_text = self.test_tweet
        
        try:
            formatted_prompt = self.prompt.format(tweet_text=tweet_text)
            
            logger.info(f"🤖 Generating with {self.current_model}...")
            
            response = self.ai_client.chat.completions.create(
                model=self.current_model,
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=0.8,
                max_tokens=800
            )
            
            if response.choices:
                content = response.choices[0].message.content.strip()
                return self.parse_comments(content)
            
        except Exception as e:
            logger.error(f"❌ Generation failed: {e}")
        
        return []
    
    def parse_comments(self, ai_response):
        """Extract comments from AI response"""
        comments = []
        for line in ai_response.split('\n'):
            line = line.strip()
            if line.startswith("COMMENT ") and ":" in line:
                comment = line.split(":", 1)[1].strip()
                if comment and len(comment) > 5:
                    comments.append(comment)
        return comments
    
    def display_comments(self, comments):
        """Show the generated comments"""
        if not comments:
            logger.error("❌ No comments generated")
            return
        
        print("\n" + "="*60)
        print(f"🎯 Generated Comments ({self.current_model})")
        print("="*60)
        
        for i, comment in enumerate(comments, 1):
            print(f"\n{i}. {comment}")
            print(f"   � {len(comment)} chars")
        
        print("\n" + "="*60)
    
    def change_model(self):
        """Change the AI model"""
        print("\n� Available models:")
        for i, model in enumerate(self.models, 1):
            current = " (current)" if model == self.current_model else ""
            print(f"  {i}. {model}{current}")
        
        try:
            choice = input(f"\nSelect model (1-{len(self.models)}): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(self.models):
                self.current_model = self.models[int(choice) - 1]
                logger.success(f"✅ Changed to {self.current_model}")
            else:
                logger.warning("Invalid choice")
        except:
            logger.warning("Invalid input")
    
    def run(self):
        """Main interactive loop"""
        print("🎨 Simple AI Prompt Checker")
        print("🎯 Test your crypto comment prompt\n")
        
        while True:
            try:
                print("\n" + "-"*40)
                print("1. Generate comments (default tweet)")
                print("2. Generate comments (custom tweet)")
                print("3. Change AI model")
                print("4. View current tweet")
                print("5. Exit")
                
                choice = input("\nChoice (1-5): ").strip()
                
                if choice == "1":
                    comments = self.generate_comments()
                    self.display_comments(comments)
                    
                elif choice == "2":
                    print("\n📝 Enter your tweet text (or paste it):")
                    print("Press Enter twice when done:\n")
                    
                    lines = []
                    empty_count = 0
                    while empty_count < 2:
                        line = input()
                        if line.strip() == "":
                            empty_count += 1
                        else:
                            empty_count = 0
                        lines.append(line)
                    
                    custom_tweet = "\n".join(lines).strip()
                    if custom_tweet:
                        comments = self.generate_comments(custom_tweet)
                        self.display_comments(comments)
                    else:
                        logger.warning("Empty tweet")
                        
                elif choice == "3":
                    self.change_model()
                    
                elif choice == "4":
                    print("\n🐦 Current test tweet:")
                    print("-" * 30)
                    print(self.test_tweet)
                    
                elif choice == "5":
                    print("\n👋 Goodbye!")
                    break
                    
                else:
                    logger.warning("Invalid choice")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                logger.error(f"💥 Error: {e}")

if __name__ == "__main__":
    checker = SimpleAIChecker()
    checker.run()
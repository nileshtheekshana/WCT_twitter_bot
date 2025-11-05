"""
🐦 Advanced Tweet Comment Generator
Generates natural crypto/finance comments in authentic community style
"""
import os
import time
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TwitterCommentGenerator:
    def __init__(self):
        """Initialize the comment generator with GitHub Models"""
        self.client = OpenAI(
            base_url="https://models.github.ai/inference",
            api_key=os.environ.get("GITHUB_TOKEN")
        )
        self.model = "openai/gpt-4o"
        self.usage_stats = {"requests_today": 0, "last_reset": datetime.now().date()}
        
    def reset_daily_usage(self):
        """Reset usage counter if it's a new day"""
        today = datetime.now().date()
        if today > self.usage_stats["last_reset"]:
            self.usage_stats["requests_today"] = 0
            self.usage_stats["last_reset"] = today
    
    def check_rate_limits(self):
        """Check if we can make a request (50/day limit for gpt-4o)"""
        self.reset_daily_usage()
        if self.usage_stats["requests_today"] >= 50:
            return False, "Daily limit of 50 requests reached. Try again tomorrow."
        return True, "OK"
    
    def update_usage(self):
        """Update usage statistics"""
        self.usage_stats["requests_today"] += 1
    
    def get_comment_prompt(self, tweet_text):
        """Generate the optimized prompt for comment generation"""
        return f"""Generate 5 natural crypto community comments for this social media post. Use this authentic style:

EXAMPLES:

Post: "AMA event announcement - Join our community space"
Comments:
- let's gooo another solid space coming up 
- never missing these events
- always good vibes in these spaces  
- already set my reminder
- these keep getting better ngl

Post: "Government officials discussing crypto adoption policies"
Comments:
- big moves happening this could be huge
- officials talking crypto? interesting
- mainstream adoption incoming fr
- some regions ahead on this stuff
- coordination getting real now

Post: "Good morning! ✌️ Are you satisfied with your investment choices? 🤔"
Comments:
- good morning
- gm fam
- morning everyone
- good morning folks
- gm crypto fam

Style Guidelines:
- Use lowercase casual style (no capitals at sentence start)
- Include crypto community language sparingly: "fr", "ngl", "imo" - use in 1-2 comments max
- Add emojis occasionally - not every comment, not always at end
- Keep comments short and punchy (one line)
- Avoid formal punctuation
- Mix normal casual speech with occasional slang
- Sound natural and varied
- For good morning posts: use simple greetings like "gm", "good morning", "morning fam", etc.

Post to comment on: {tweet_text}

Provide exactly 5 comments in this format:
COMMENT 1: [comment]
COMMENT 2: [comment] 
COMMENT 3: [comment]
COMMENT 4: [comment]
COMMENT 5: [comment]"""

    def generate_comments(self, tweet_text):
        """Generate 5 natural comments for a tweet"""
        # Check rate limits
        can_request, message = self.check_rate_limits()
        if not can_request:
            return f"❌ {message}"
        
        try:
            prompt = self.get_comment_prompt(tweet_text)
            
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful assistant that generates natural, casual social media comments for cryptocurrency and technology posts. Focus on positive, community-oriented responses."
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                max_tokens=400,
                temperature=0.7  # Balanced creativity
            )
            
            # Update usage stats
            self.update_usage()
            
            result = response.choices[0].message.content
            
            # Add usage info
            remaining = 50 - self.usage_stats["requests_today"]
            result += f"\n\n📊 Usage: {self.usage_stats['requests_today']}/50 requests today | {remaining} remaining"
            
            return result
            
        except Exception as e:
            return f"❌ Error generating comments: {str(e)}"
    
    def save_results(self, tweet, comments, filename=None):
        """Save generated comments to a file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comments_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("🐦 GENERATED TWEET COMMENTS\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"📝 TWEET:\n{tweet}\n\n")
                f.write(f"💬 COMMENTS:\n{comments}\n\n")
                f.write(f"🕒 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            return f"✅ Results saved to: {filename}"
        except Exception as e:
            return f"❌ Failed to save: {str(e)}"

def load_tweets_from_file():
    """Load tweets from tweet.txt or return predefined ones"""
    predefined_tweets = [
        'LATEST🚨\n\nThe White House says President Trump has "officially ended the Biden administration\'s war on the cryptocurrency industry."🇺🇸',
        '@Pecunity_app\'s vesting round goes live today at 5PM UTC for a 48-hour window.⏰\n\nStarting up to 50% below TGE price, with a rising price curve as the allocation fills. Vesting terms include a 6-month period and 25% unlock at launch.\n\nLearn more here↘️#PEC #Pecunity #NFA\nhttps://sale.pecunity.io',
        'LATEST🚨\n\nKraken enables crypto collateral for derivatives trading across the EU.🇪🇺',
        'Crypto futures liquidations have surpassed $1.13 Billion in the past 24 hours as #Bitcoin drops below $106,000.📉\n\nLONGs alone accounted for $1.05 Billion.🔺💰',
        'JUST IN🚨\n\nOpenAI signs a $38 billion deal with Amazon Web Services.🌐\n\nThe partnership grants OpenAI immediate access to Nvidia GPUs and scalable compute capacity through 2026.💡',
        'AMA ANNOUNCEMENT📢\n\n➡️Join: http://t.me/whalecointalk\n➡️Follow: @mobymedia\n🏦Join our X Space with @WCTNoah\n\nDon\'t miss out!\nVerify team @mobymedia | http://linktr.ee/mobymedia'
    ]
    
    try:
        if os.path.exists('tweet.txt'):
            print("📁 tweet.txt found - using predefined tweets for reliability")
        return predefined_tweets
    except:
        return predefined_tweets

def display_menu():
    """Display the main menu"""
    print("\n" + "="*60)
    print("🐦 ADVANCED TWEET COMMENT GENERATOR")
    print("="*60)
    print("🤖 Model: GPT-4o (High Quality)")
    print("⚡ Rate Limit: 50 requests/day")
    print("🎯 Style: Authentic crypto community")
    print("="*60)
    print("\n📋 OPTIONS:")
    print("1️⃣  Generate for single tweet")
    print("2️⃣  Generate for all tweets")
    print("3️⃣  Enter custom tweet")
    print("4️⃣  View usage stats")
    print("5️⃣  Exit")
    print("-"*60)

def main():
    """Main application loop"""
    generator = TwitterCommentGenerator()
    tweets = load_tweets_from_file()
    
    print("🚀 Twitter Comment Generator Initialized!")
    print(f"📝 Loaded {len(tweets)} tweets")
    
    while True:
        display_menu()
        choice = input("➤ Choose option (1-5): ").strip()
        
        if choice == "1":
            # Single tweet
            print(f"\n📋 Available tweets:")
            for i, tweet in enumerate(tweets, 1):
                preview = tweet.replace('\n', ' ')[:80] + "..." if len(tweet) > 80 else tweet.replace('\n', ' ')
                print(f"{i}. {preview}")
            
            try:
                selection = int(input(f"\n➤ Choose tweet (1-{len(tweets)}): "))
                if 1 <= selection <= len(tweets):
                    selected_tweet = tweets[selection - 1]
                    
                    print(f"\n🐦 SELECTED TWEET:")
                    print("-" * 50)
                    print(selected_tweet)
                    print("-" * 50)
                    
                    print("\n🤖 Generating comments...")
                    comments = generator.generate_comments(selected_tweet)
                    
                    print("\n✅ GENERATED COMMENTS:")
                    print(comments)
                    
                    # Option to save
                    save = input("\n💾 Save results to file? (y/n): ").lower()
                    if save == 'y':
                        result = generator.save_results(selected_tweet, comments)
                        print(result)
                        
                else:
                    print("❌ Invalid selection!")
            except ValueError:
                print("❌ Please enter a valid number!")
        
        elif choice == "2":
            # All tweets
            print(f"\n🚀 Generating comments for all {len(tweets)} tweets...")
            
            for i, tweet in enumerate(tweets, 1):
                print(f"\n{'='*60}")
                print(f"🐦 TWEET {i}/{len(tweets)}:")
                print("-" * 40)
                preview = tweet.replace('\n', ' ')[:100] + "..." if len(tweet) > 100 else tweet.replace('\n', ' ')
                print(f"📄 {preview}")
                print("-" * 40)
                
                print("🤖 Generating comments...")
                comments = generator.generate_comments(tweet)
                print("✅ Generated Comments:")
                print(comments)
                
                # Save each result
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"comments_tweet_{i}_{timestamp}.txt"
                generator.save_results(tweet, comments, filename)
                
                if i < len(tweets):
                    print("\n⏳ Waiting 3 seconds to respect rate limits...")
                    time.sleep(3)
            
            print("\n🎉 All tweets processed!")
        
        elif choice == "3":
            # Custom tweet
            print("\n📝 Enter your custom tweet:")
            custom_tweet = input("➤ Tweet: ").strip()
            
            if custom_tweet:
                print(f"\n🐦 YOUR TWEET:")
                print("-" * 50)
                print(custom_tweet)
                print("-" * 50)
                
                print("\n🤖 Generating comments...")
                comments = generator.generate_comments(custom_tweet)
                
                print("\n✅ GENERATED COMMENTS:")
                print(comments)
                
                # Option to save
                save = input("\n💾 Save results to file? (y/n): ").lower()
                if save == 'y':
                    result = generator.save_results(custom_tweet, comments)
                    print(result)
            else:
                print("❌ No tweet entered!")
        
        elif choice == "4":
            # Usage stats
            generator.reset_daily_usage()
            remaining = 50 - generator.usage_stats["requests_today"]
            
            print(f"\n📊 USAGE STATISTICS:")
            print("-" * 40)
            print(f"📈 Requests today: {generator.usage_stats['requests_today']}/50")
            print(f"⚡ Remaining: {remaining}")
            print(f"📅 Reset date: {generator.usage_stats['last_reset']}")
            print(f"🤖 Model: {generator.model}")
            print("-" * 40)
        
        elif choice == "5":
            print("\n👋 Thanks for using Tweet Comment Generator!")
            print("🚀 Happy tweeting!")
            break
        
        else:
            print("❌ Invalid option! Please choose 1-5.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("Please check your .env file and internet connection.")
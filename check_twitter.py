#!/usr/bin/env python3
"""
Twitter API Keys Checker
Standalone program to test all Twitter API keys by reading a specific tweet
"""

import os
import sys
from dotenv import load_dotenv
import tweepy
from loguru import logger
import time

# Load environment variables
load_dotenv()

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

class TwitterAPIChecker:
    """Test all Twitter API keys by reading a specific tweet"""
    
    def __init__(self):
        self.test_tweet_url = "https://x.com/kucoincom/status/1972602255577907595"
        self.test_tweet_id = "1972602255577907595"
        self.clients = {}
        self.results = {}
        
    def load_credentials(self):
        """Load all Twitter API credentials from .env file"""
        try:
            # Main account credentials
            main_creds = {
                'consumer_key': os.getenv('TWITTER_CONSUMER_KEY'),
                'consumer_secret': os.getenv('TWITTER_CONSUMER_SECRET'),
                'access_token': os.getenv('TWITTER_ACCESS_TOKEN'),
                'access_token_secret': os.getenv('TWITTER_ACCESS_TOKEN_SECRET'),
                'bearer_token': os.getenv('TWITTER_BEARER_TOKEN')
            }
            
            if all(main_creds.values()):
                self.clients['main'] = main_creds
                logger.info("✅ Main account credentials loaded")
            else:
                logger.warning("❌ Main account credentials incomplete")
            
            # Read accounts (1-5) - using the actual .env variable names
            for i in range(1, 6):
                read_creds = {
                    'consumer_key': os.getenv(f'TWITTER_CONSUMER_KEY{i}'),
                    'consumer_secret': os.getenv(f'TWITTER_CONSUMER_SECRET{i}'),
                    'access_token': os.getenv(f'TWITTER_ACCESS_TOKEN{i}'),
                    'access_token_secret': os.getenv(f'TWITTER_ACCESS_TOKEN_SECRET{i}'),
                    'bearer_token': os.getenv(f'TWITTER_BEARER_TOKEN{i}')
                }
                
                if all(read_creds.values()):
                    self.clients[f'read_{i}'] = read_creds
                    logger.info(f"✅ Read account {i} credentials loaded")
                else:
                    logger.warning(f"❌ Read account {i} credentials incomplete or missing")
            
            logger.info(f"📊 Total accounts loaded: {len(self.clients)}")
            return len(self.clients) > 0
            
        except Exception as e:
            logger.error(f"💥 Error loading credentials: {e}")
            return False
    
    def create_tweepy_client(self, account_name, credentials):
        """Create a Tweepy client with given credentials"""
        try:
            # Try with Bearer Token first (v2 API)
            if credentials.get('bearer_token'):
                client = tweepy.Client(
                    bearer_token=credentials['bearer_token'],
                    consumer_key=credentials['consumer_key'],
                    consumer_secret=credentials['consumer_secret'],
                    access_token=credentials['access_token'],
                    access_token_secret=credentials['access_token_secret'],
                    wait_on_rate_limit=False
                )
                return client
            else:
                logger.warning(f"⚠️ No bearer token for {account_name}")
                return None
                
        except Exception as e:
            logger.error(f"💥 Error creating client for {account_name}: {e}")
            return None
    
    def test_tweet_reading(self, account_name, client):
        """Test reading the specific tweet with given client"""
        try:
            logger.info(f"🔍 Testing {account_name} - Reading tweet {self.test_tweet_id}...")
            
            # Try to get the tweet
            tweet = client.get_tweet(
                id=self.test_tweet_id,
                tweet_fields=['created_at', 'author_id', 'public_metrics', 'text']
            )
            
            if tweet.data:
                tweet_data = tweet.data
                logger.success(f"✅ {account_name} - Successfully read tweet!")
                logger.info(f"   📝 Text: {tweet_data.text[:100]}...")
                logger.info(f"   👤 Author ID: {tweet_data.author_id}")
                logger.info(f"   📅 Created: {tweet_data.created_at}")
                if tweet_data.public_metrics:
                    metrics = tweet_data.public_metrics
                    logger.info(f"   📊 Metrics: {metrics['like_count']} likes, {metrics['retweet_count']} retweets")
                
                return {
                    'status': 'success',
                    'tweet_text': tweet_data.text,
                    'author_id': tweet_data.author_id,
                    'created_at': str(tweet_data.created_at),
                    'metrics': tweet_data.public_metrics if tweet_data.public_metrics else {}
                }
            else:
                logger.error(f"❌ {account_name} - No tweet data received")
                return {'status': 'error', 'error': 'No tweet data received'}
                
        except tweepy.TooManyRequests as e:
            logger.error(f"⚠️ {account_name} - Rate limit exceeded")
            return {'status': 'rate_limited', 'error': 'Rate limit exceeded'}
            
        except tweepy.Unauthorized as e:
            logger.error(f"❌ {account_name} - Unauthorized (invalid credentials)")
            return {'status': 'unauthorized', 'error': 'Invalid credentials'}
            
        except tweepy.Forbidden as e:
            logger.error(f"❌ {account_name} - Forbidden (access denied)")
            return {'status': 'forbidden', 'error': 'Access denied'}
            
        except tweepy.NotFound as e:
            logger.error(f"❌ {account_name} - Tweet not found")
            return {'status': 'not_found', 'error': 'Tweet not found'}
            
        except Exception as e:
            logger.error(f"💥 {account_name} - Unexpected error: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def run_tests(self):
        """Run tests on all loaded Twitter accounts"""
        if not self.load_credentials():
            logger.error("💥 No credentials loaded. Check your .env file!")
            return False
        
        logger.info(f"🚀 Starting Twitter API tests...")
        logger.info(f"🎯 Target tweet: {self.test_tweet_url}")
        logger.info("=" * 60)
        
        success_count = 0
        total_count = len(self.clients)
        
        for account_name, credentials in self.clients.items():
            logger.info(f"\n🧪 Testing account: {account_name}")
            logger.info("-" * 40)
            
            # Create client
            client = self.create_tweepy_client(account_name, credentials)
            if not client:
                self.results[account_name] = {'status': 'client_creation_failed', 'error': 'Could not create client'}
                continue
            
            # Test tweet reading
            result = self.test_tweet_reading(account_name, client)
            self.results[account_name] = result
            
            if result['status'] == 'success':
                success_count += 1
            
            # Small delay between tests to avoid rate limits
            time.sleep(1)
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 TWITTER API TEST SUMMARY")
        logger.info("=" * 60)
        
        for account_name, result in self.results.items():
            status = result['status']
            if status == 'success':
                logger.success(f"✅ {account_name:15} - WORKING")
            elif status == 'rate_limited':
                logger.warning(f"⚠️ {account_name:15} - RATE LIMITED")
            elif status == 'unauthorized':
                logger.error(f"❌ {account_name:15} - INVALID CREDENTIALS")
            elif status == 'forbidden':
                logger.error(f"❌ {account_name:15} - ACCESS DENIED")
            elif status == 'not_found':
                logger.error(f"❌ {account_name:15} - TWEET NOT FOUND")
            else:
                logger.error(f"💥 {account_name:15} - ERROR: {result.get('error', 'Unknown')}")
        
        logger.info("-" * 60)
        logger.info(f"📈 Results: {success_count}/{total_count} accounts working")
        logger.info(f"🎯 Success rate: {(success_count/total_count)*100:.1f}%")
        
        if success_count == total_count:
            logger.success("🎉 All Twitter API keys are working perfectly!")
        elif success_count > 0:
            logger.warning(f"⚠️ {total_count - success_count} account(s) have issues")
        else:
            logger.error("💥 No Twitter API keys are working!")
        
        return success_count > 0

def main():
    """Main function"""
    try:
        logger.info("🔧 Twitter API Keys Checker")
        logger.info("🎯 Testing tweet: https://x.com/kucoincom/status/1972602255577907595")
        logger.info("📁 Loading credentials from .env file...")
        
        checker = TwitterAPIChecker()
        success = checker.run_tests()
        
        if success:
            logger.success("\n✅ Twitter API check completed!")
        else:
            logger.error("\n❌ Twitter API check failed!")
            
        return success
        
    except KeyboardInterrupt:
        logger.warning("\n⏹️ Twitter API check interrupted by user")
        return False
    except Exception as e:
        logger.error(f"\n💥 Unexpected error: {e}")
        return False

if __name__ == "__main__":
    main()
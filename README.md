# Twitter Shilling Bot

An intelligent automated bot that monitors Telegram channels for Twitter engagement jobs, validates them using AI, generates creative comments, and manages multi-account Twitter interactions with advanced rate limiting.

## 🚀 Key Features

- **Intelligent Job Monitoring**: 24/7 Telegram channel monitoring with AI-powered job validation
- **Multi-Account Management**: 6-account Twitter system (1 main + 5 read accounts) with intelligent rate limiting
- **AI-Powered Comments**: Generates exactly 5 realistic, human-like comments using Groq AI
- **Interactive Selection**: Telegram button-based comment selection system
- **Personal Telegram Integration**: Seamless job monitoring through personal Telegram client
- **Comprehensive Logging**: Detailed activity tracking and error handling
- **VPS-Optimized**: Ready for deployment on Linux VPS with automated setup scripts

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Personal      │───▶│   Job Detection  │───▶│   AI Validation │
│   Telegram      │    │   & Monitoring   │    │   (Groq)       │
│   Client        │    └──────────────────┘    └─────────────────┘
└─────────────────┘              │                       │
                                 ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Comment       │◀───│   Twitter API    │◀───│   Comment       │
│   Selection     │    │   Multi-Account  │    │   Generation    │
│   (Buttons)     │    │   Manager        │    │   (AI-Powered)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🛠️ Quick Setup

### Windows
1. Run `setup_windows.bat`
2. Copy `.env.example` to `.env` and fill in your credentials
3. Activate virtual environment: `venv\Scripts\activate`
4. Run the bot: `python main.py`

### Linux/VPS
1. Run `chmod +x setup_linux.sh && ./setup_linux.sh`
2. Copy `.env.example` to `.env` and fill in your credentials
3. Activate virtual environment: `source venv/bin/activate`
4. Run the bot: `python main.py`

## Configuration

Copy `.env.example` to `.env` and configure the following:

### Required Settings
- **Telegram**: Bot token, channel/group IDs, user ID
- **Groq AI**: API key for job validation and comment generation
- **Twitter**: Main account credentials (for posting)
- **Twitter Read Accounts**: Up to 5 additional accounts for reading tweets

### Environment Variables

```bash
# Telegram Configuration
TELEGRAM_MAIN_CHANNEL_ID=          # Channel where jobs are posted
TELEGRAM_MAIN_GROUP_ID=            # Group for submitting results  
TELEGRAM_BOT_TOKEN=                # Your bot token
TELEGRAM_NOTIFICATION_GROUP_ID=    # Group for notifications
TELEGRAM_USER_ID=                  # Your Telegram user ID

# AI Configuration  
AI_API_KEY=                        # Groq API key

# Twitter Main Account (reading + writing)
TWITTER_CONSUMER_KEY=
TWITTER_CONSUMER_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_TOKEN_SECRET=
TWITTER_CLIENT_ID=
TWITTER_CLIENT_SECRET=
TWITTER_BEARER_TOKEN=

# Twitter Read Accounts 1-5 (reading only)
TWITTER_CONSUMER_KEY1=
TWITTER_CONSUMER_SECRET1=
TWITTER_ACCESS_TOKEN1=
TWITTER_ACCESS_TOKEN_SECRET1=
TWITTER_CLIENT_ID1=
TWITTER_CLIENT_SECRET1=
TWITTER_BEARER_TOKEN1=

# ... repeat for accounts 2-5
```

## How It Works

1. **Monitoring**: Continuously monitors specified Telegram channel for new messages
2. **Validation**: Uses Groq AI to validate if message is a legitimate Twitter job
3. **Reading**: Extracts Twitter URL and reads tweet content using rotating API accounts
4. **Generation**: Creates 3 unique comments using AI and randomly selects one
5. **Posting**: Posts the selected comment as a reply using main Twitter account
6. **Submission**: Submits the comment link back to Telegram group
7. **Reporting**: Sends comprehensive report with all details

## Valid Job Format

The bot looks for jobs with this structure:
```
R133 - REQUIRED TASK NUMBER [ 73 ] ✍️

Date Mon,2025-09-29
Duration 24hrs 🕒

Title: Twitter Impression

LINK: https://x.com/username/status/1234567890

⭕️ Please be creative and post individual responses.

NOTE: Please save the link to your Comment to submit your proof of work at the end of the Round.
```

## Project Structure

```
twitter_shilling_bot/
├── src/
│   ├── ai_validator.py      # Groq AI integration
│   ├── twitter_manager.py   # Twitter API management
│   ├── telegram_manager.py  # Telegram integration
│   ├── config.py           # Configuration loader
│   ├── utils.py            # Utility functions
│   └── logger_setup.py     # Logging configuration
├── logs/                   # Log files
├── main.py                # Main application
├── requirements.txt       # Dependencies
├── .env.example          # Environment template
├── setup_windows.bat     # Windows setup
└── setup_linux.sh       # Linux setup
```

## API Limits & Management

- **Twitter**: 100 reads + 400 writes per account per month
- **Strategy**: 5 read accounts = 500 reads total, 1 write account = 400 writes
- **Rate Limiting**: Automatic rotation and retry logic
- **Monitoring**: Usage tracking and reporting

## Logging

Logs are stored in the `logs/` directory:
- `twitter_bot_YYYY-MM-DD.log` - General application logs
- `errors_YYYY-MM-DD.log` - Error-only logs  
- `jobs_YYYY-MM-DD.log` - Job processing activities

## VPS Deployment

1. Clone/upload to VPS
2. Run setup script: `./setup_linux.sh`
3. Configure `.env` file
4. Run with screen/tmux: `screen -S twitter_bot python main.py`
5. Monitor logs: `tail -f logs/twitter_bot_$(date +%Y-%m-%d).log`

## Troubleshooting

### Common Issues

1. **Twitter API Errors**: Check credentials and rate limits
2. **Telegram Bot Issues**: Verify bot token and permissions
3. **AI Validation Fails**: Check Groq API key and quota
4. **Import Errors**: Ensure virtual environment is activated

### Debug Mode
Set `LOG_LEVEL=DEBUG` in `.env` for detailed logging.

### Support
Check the logs directory for detailed error information and troubleshooting.

## Safety Features

- Input validation and sanitization
- Rate limit protection
- Error handling and recovery
- Graceful shutdown on signals
- Comprehensive logging for debugging

## License

This project is for educational purposes. Ensure compliance with platform terms of service.
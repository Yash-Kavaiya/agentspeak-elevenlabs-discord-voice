# Gemini Discord Voice Agent

A real-time conversational AI bot that integrates Google Gemini Live API with Discord voice channels. When users join a voice channel, the bot automatically joins, greets them, and answers their queries in real-time using voice.

## Features

- **Auto-Join Voice Channels**: Bot automatically joins when users enter voice channels
- **Real-Time Voice Conversation**: Uses Google Gemini Live API for natural voice interactions
- **Voice-to-Voice Communication**: Captures user speech and responds with AI-generated voice
- **Customizable Greetings**: Greet users when they join the voice channel
- **Multi-Channel Support**: Handle conversations in multiple voice channels simultaneously
- **Text Commands**: Also supports text-based interaction via Discord commands

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Discord Voice Channel                        │
│  ┌──────────────┐                         ┌──────────────┐      │
│  │ User Speech  │                         │ Bot Response │      │
│  └──────┬───────┘                         └──────▲───────┘      │
└─────────┼────────────────────────────────────────┼──────────────┘
          │                                        │
          ▼                                        │
┌─────────────────────────────────────────────────────────────────┐
│                        Discord Bot                               │
│  ┌──────────────────┐              ┌──────────────────┐         │
│  │  Audio Sink      │              │  Audio Source    │         │
│  │  (Voice Recv)    │              │  (Voice Play)    │         │
│  └────────┬─────────┘              └────────▲─────────┘         │
│           │                                  │                   │
│           ▼                                  │                   │
│  ┌──────────────────────────────────────────────────────┐       │
│  │            Discord Audio Interface                    │       │
│  │   - Convert 48kHz Stereo → 16kHz Mono (input)        │       │
│  │   - Convert 24kHz Mono → 48kHz Stereo (output)       │       │
│  └──────────────────────┬───────────────────▲───────────┘       │
└─────────────────────────┼───────────────────┼───────────────────┘
                          │                   │
                          ▼                   │
┌─────────────────────────────────────────────────────────────────┐
│                   Google Gemini Live API                         │
│  ┌──────────────────┐              ┌──────────────────┐         │
│  │   Audio Input    │──────────────▶│   Gemini AI     │         │
│  │   (User Voice)   │              │   Processing    │         │
│  └──────────────────┘              └────────┬─────────┘         │
│                                              │                   │
│                                    ┌────────▼─────────┐         │
│                                    │   Audio Output   │         │
│                                    │   (AI Response)  │         │
│                                    └──────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### System Requirements

- Python 3.10 or higher
- FFmpeg installed on your system

### API Keys Required

1. **Discord Bot Token**: Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
2. **Google API Key**: Get an API key from [Google AI Studio](https://aistudio.google.com/apikey)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Yash-Kavaiya/discord-adk-live-api.git
cd discord-adk-live-api
```

### 2. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y ffmpeg libffi-dev libnacl-dev python3-dev
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
- Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

### 3. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Required
DISCORD_BOT_TOKEN=your_discord_bot_token_here
GOOGLE_API_KEY=your_google_api_key_here

# Optional
GEMINI_MODEL=gemini-2.5-flash-native-audio-preview-12-2025
AUTO_JOIN_VOICE=true
GREETING_ENABLED=true
GREETING_MESSAGE=Hello! I'm your AI assistant. How can I help you today?
DEBUG=false
```

## Setting Up Discord Bot

### 1. Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. Copy the Bot Token and add to your `.env` file

### 2. Configure Bot Permissions

Required permissions:
- **View Channels**
- **Send Messages**
- **Connect** (Voice)
- **Speak** (Voice)
- **Use Voice Activity**

OAuth2 URL Generator scopes:
- `bot`
- `applications.commands`

### 3. Enable Required Intents

In the Bot section, enable:
- **Server Members Intent**
- **Message Content Intent**

### 4. Invite Bot to Server

Use the OAuth2 URL Generator with the above permissions and scopes, then invite to your server.

## Gemini Model

This project uses the Gemini Live API with native audio support. The recommended model is:

- `gemini-2.5-flash-native-audio-preview-12-2025` - Fast native audio model

### Audio Specifications

- **Input**: 16kHz mono PCM audio from Discord (converted from 48kHz stereo)
- **Output**: 24kHz mono PCM audio from Gemini (converted to 48kHz stereo for Discord)

## Usage

### Running the Bot

```bash
# Basic run
python main.py

# With CLI options
python run.py --debug --greeting "Welcome to the voice channel!"
```

### Bot Commands

| Command | Description |
|---------|-------------|
| `!join` | Join your current voice channel |
| `!leave` | Leave the voice channel |
| `!ask <question>` | Ask the AI a text question |
| `!stop` | Interrupt the AI while speaking |
| `!status` | Show bot status |

### Voice Interaction

1. Join a voice channel
2. The bot will automatically join (if `AUTO_JOIN_VOICE=true`)
3. Speak naturally - the bot will listen and respond
4. The AI will respond with voice

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | Required | Discord bot authentication token |
| `GOOGLE_API_KEY` | Required | Google API key for Gemini |
| `GEMINI_MODEL` | See default | Gemini model to use |
| `AUTO_JOIN_VOICE` | `true` | Auto-join when users join voice |
| `GREETING_ENABLED` | `true` | Greet users when they join |
| `GREETING_MESSAGE` | See default | Custom greeting message |
| `DEBUG` | `false` | Enable debug logging |

### CLI Arguments

```bash
python run.py --help

Options:
  --token          Discord bot token
  --api-key        Google API key
  --model          Gemini model to use
  --no-auto-join   Disable auto-joining
  --no-greeting    Disable greetings
  --greeting TEXT  Custom greeting message
  --debug          Enable debug logging
  --prefix CHAR    Command prefix (default: !)
```

## Project Structure

```
discord-adk-live-api/
├── src/
│   ├── __init__.py
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── audio_buffer.py          # Thread-safe audio buffer
│   │   ├── discord_audio_interface.py # Discord ↔ Gemini audio bridge
│   │   └── discord_audio_source.py   # Audio source for Discord playback
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── audio_sink.py            # Audio sink for receiving Discord audio
│   │   └── voice_bot.py             # Main Discord bot implementation
│   └── gemini_agent/
│       ├── __init__.py
│       └── agent.py                 # Gemini Live API agent
├── main.py                          # Main entry point
├── run.py                           # CLI entry point with arguments
├── requirements.txt                 # Python dependencies
├── .env.example                     # Example environment configuration
└── README.md                        # This file
```

## Troubleshooting

### Bot joins but no audio

1. Ensure FFmpeg is installed: `ffmpeg -version`
2. Check that PyNaCl is installed: `pip install pynacl`
3. Verify bot has "Speak" permission in the voice channel

### No voice recognition

1. Install discord-ext-voice-recv: `pip install discord-ext-voice-recv`
2. Ensure bot has "Use Voice Activity" permission
3. Check microphone permissions in Discord

### Gemini connection issues

1. Verify your Google API key is correct
2. Ensure the model name is correct
3. Ensure stable internet connection

### High latency

1. Use a closer server region
2. Check network connection quality
3. The flash model is optimized for lower latency

## API Documentation References

- [Google Gemini Live API](https://ai.google.dev/gemini-api/docs/live)
- [Google ADK Streaming](https://google.github.io/adk-docs/get-started/streaming/quickstart-streaming/)
- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [discord-ext-voice-recv](https://github.com/imayhaveborkedit/discord-ext-voice-recv)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [Google](https://ai.google.dev) for the Gemini AI platform
- [discord.py](https://github.com/Rapptz/discord.py) for the Discord API wrapper
- [discord-ext-voice-recv](https://github.com/imayhaveborkedit/discord-ext-voice-recv) for voice receiving capabilities

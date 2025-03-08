# AI Home Assistant Backend

A voice-enabled AI home assistant using FastAPI, OpenAI, Deepgram, Azure Speech Services, and OpenWeather API.

## Features

- Voice interaction with wake word detection
- Speech-to-Text using Deepgram
- Text-to-Speech using Azure Speech Services
- WebSocket-based real-time communication
- AI integration with OpenAI for intelligent responses
- Weather information via OpenWeather API
- Multi-model AI support for different types of queries

## Setup

### Option 1: Using the Setup Script (Recommended)

1. Clone the repository
```bash
git clone <your-repository-url>
cd <project-directory>
```

2. Make the setup script executable
```bash
chmod +x setup.sh
```

3. Run the setup script
```bash
./setup.sh
```

4. Follow the on-screen prompts to select your setup option:
   - Option 1: Full setup (frontend and backend)
   - Option 2: Frontend only
   - Option 3: Backend only

5. After completion, activate the virtual environment
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

6. Create .env file with your credentials
```bash
# OpenAI API credentials
OPENAI_API_KEY=your_key_here

# Azure Speech Services credentials
AZURE_SPEECH_KEY=your_key_here
AZURE_SPEECH_REGION=your_region_here

# Deepgram API credentials
DEEPGRAM_API_KEY=your_key_here

# OpenWeather API credentials
OPENWEATHER_API_KEY=your_key_here
```

7. Run the server
```bash
python main.py
```

### Option 2: Manual Setup

1. Clone the repository
```bash
git clone <your-repository-url>
cd aihome/backend
```

2. Create and activate virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Create .env file with your credentials
```bash
# OpenAI API credentials
OPENAI_API_KEY=your_key_here

# Azure Speech Services credentials
AZURE_SPEECH_KEY=your_key_here
AZURE_SPEECH_REGION=your_region_here

# Deepgram API credentials
DEEPGRAM_API_KEY=your_key_here

# OpenWeather API credentials
OPENWEATHER_API_KEY=your_key_here
```

5. Run the server
```bash
python main.py
```

## API Documentation

Once running, visit http://localhost:8000/docs for the interactive API documentation.

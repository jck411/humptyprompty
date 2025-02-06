# AI Home Assistant Backend

A voice-enabled AI home assistant using FastAPI, OpenAI, and Azure Speech Services.

## Features

- Voice interaction with wake word detection
- Speech-to-Text and Text-to-Speech capabilities
- WebSocket-based real-time communication
- OpenAI integration for intelligent responses

## Setup

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
OPENAI_API_KEY=your_key_here
AZURE_SPEECH_KEY=your_key_here
AZURE_SPEECH_REGION=your_region_here
```

5. Run the server
```bash
python main.py
```

## API Documentation

Once running, visit http://localhost:8000/docs for the interactive API documentation.

# Smart Display Frontend (PySide6 + QML)

This is the frontend implementation for the Smart Display project, built with PySide6 and QML.

## Structure

- `client.py` - Main entry point that runs the PySide6 application
- `main.qml` - Main QML window with StackView for screen navigation
- `screens/` - Individual screen implementations
  - `ChatScreen.qml` - Chat interface with AI assistant
  - Other placeholder screens for future implementation
- `components/` - Reusable QML components
  - `MessageBubble.qml` - For displaying chat messages
  - `CustomTextInput.qml` - Text input field with special handling
  - `IconButton.qml` - Buttons with icons and visual effects
- `models/` - Python models for backend communication
  - `ChatModel.py` - Handles WebSocket communication with backend
  - `AudioManager.py` - Manages TTS audio playback

## Setup

1. Install dependencies:
```bash
pip install -r frontend/requirements.txt
```

2. Make sure the backend server is running:
```bash
cd backend/
python main.py
```

3. Run the frontend:
```bash
cd frontend/
python client.py
```

## Features

- Real-time chat with AI assistant
- Speech-to-Text (STT) and Text-to-Speech (TTS) capabilities
- Dark/Light theme switching
- WebSocket-based communication with the backend

## Development

To compile the resource file (if icons are changed):
```bash
pyside6-rcc frontend/resources.qrc -o frontend/resources.py
```

Then import the resources in client.py:
```python
import frontend.resources

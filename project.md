# Smart Display Frontend (PySide6 + QML)

## Overview
This project is a **Raspberry Pi-based smart display frontend** built using **PySide6 (Python) and QML (UI)**. It functions as a multi-screen home information hub, integrating with a **FastAPI backend** to provide AI chat, TTS, weather, calendar events, and photo displays.

## System Architecture
### 1. **Backend Server (Already Developed)**
- **Technology:** FastAPI (Python)
- **Services Provided:**
  - AI Chat (LLM-based)
  - Text-to-Speech (TTS) audio generation
  - WebSocket-based real-time communication
- **Role:** Handles AI interactions, speech synthesis, and APIs for external services.

### 2. **Frontend Client (PySide6 + QML)**
- **Technology:** PySide6 (Python) for logic, QML for UI
- **Role:** Displays and manages screens, fetches data, and communicates with the backend

### 3. **Data Flow Between Frontend & Backend**
1. The **frontend requests** calendar events, weather data, and photos from external services.
2. The **frontend sends** chat messages to the backend via WebSocket.
3. The **backend responds** with AI-generated text and optional TTS audio.
4. The **frontend updates** the chat UI and plays audio responses.

## Application Architecture
### **1. Single-Window, Multi-Screen Design**
- **Single QML Window**: The entire UI runs within one fullscreen window.
- **StackView / Dynamic Loader**: Manages different screens (clock, calendar, weather, etc.).
- **Timer-Controlled Rotation**: Screens rotate automatically based on a set interval.
- **User Interaction**: Users can manually navigate between screens using touch/gestures.

### **2. Directory Structure**
```
frontend/
├── client.py             # PySide6 main entry point
├── main.qml              # Main UI with StackView
├── screens/              # Individual QML screens
│   ├── ClockScreen.qml   # Clock display
│   ├── WeatherScreen.qml # Weather info (OpenWeather API)
│   ├── CalendarScreen.qml# Google Calendar events
│   ├── PhotosScreen.qml  # Google Photos slideshow
│   ├── ChatScreen.qml    # AI chat with LLM & TTS
│   ├── SettingsScreen.qml# User settings (future expansion)
├── models/               # Python logic layer
│   ├── chat.py           # WebSocket communication with backend
│   ├── weather.py        # Fetches OpenWeather data
│   ├── calendar.py       # Fetches Google Calendar events
│   ├── photos.py         # Handles Google Photos integration
│   ├── config.py         # Configuration management
└── assets/               # UI assets (icons, fonts, sounds)
```

### **3. Core Functionalities**
#### **A. Google Calendar Screen**
- Displays upcoming events from a connected Google account.
- Fetches and updates data in real-time.
- Supports scrolling and event details.

#### **B. Weather Screen (OpenWeather API)**
- Shows current weather conditions and future forecasts.
- Updates dynamically based on API data.

#### **C. Photos Screen (Google Photos API)**
- Displays a slideshow of personal or shared Google Photos.
- Supports transitions and user-controlled navigation.

#### **D. Clock Screen**
- Displays real-time digital or analog clock.
- Updates every second.

#### **E. Chat Screen (AI Assistant)**
- Sends and receives chat messages via WebSocket.
- Displays AI responses and plays TTS-generated audio.

### **4. Integration Between PySide6 and QML**
- **PySide6 handles:**
  - WebSocket communication with backend.
  - API requests for weather, calendar, and photos.
  - Managing and exposing data to QML.

- **QML handles:**
  - UI rendering and animations.
  - Displaying screens dynamically.
  - Sending user interactions to Python.

### **5. Future Expandability**
- Smart Home Control (e.g., Zigbee integration for lights, thermostat control)
- News & Stock Market Updates
- Motion Detection (auto-wake on user presence)
- Voice Wake Word for hands-free operation
- Multi-User Profiles for personalized content

## Deployment & Setup
1. **Run the Backend Server:**
   ```bash
   cd backend/
   python main.py
   ```
2. **Run the Frontend Client:**
   ```bash
   cd frontend/
   python client.py
   ```

## Summary
- **Modular Design:** Each screen is independent and can be extended.
- **Optimized for Raspberry Pi:** Lightweight, single-window design ensures stability.
- **Seamless Backend Integration:** Uses WebSockets for real-time AI chat and data fetching.
- **Smooth UI Experience:** QML animations and StackView for transitions.

This architecture ensures **high performance, scalability, and a modern user experience** while keeping it easy to maintain and expand.


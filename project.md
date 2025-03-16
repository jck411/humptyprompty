

# Smart Display Project Overview

## Project Goal
Create a Raspberry Pi-based smart display that functions as a home information hub, showing various screens that rotate automatically. The display will show time, weather, calendar events, photos, and include a chat interface for interacting with an AI assistant.

## Key Features
- **Multi-screen Interface**: Rotating display showing different information screens
- **Clock Screen**: Shows current time and date in a large, readable format
- **Weather Screen**: Displays current weather conditions and forecast
- **Calendar Screen**: Shows upcoming events from connected calendars
- **Photo Screen**: Displays a slideshow of photos from configured sources
- **Chat Interface**: Allows interaction with an AI assistant using text and voice

## Technical Architecture

### Directory Structure
```
frontend/
├── __init__.py
├── client.py                  # Main entry point
├── base_window.py             # New base window class
├── window_manager.py          # New window manager
├── chat_window.py             # Modified existing chat window
├── clock_window.py            # New clock window
├── weather_window.py          # New weather window
├── calendar_window.py         # New calendar window
├── photo_window.py            # New photo window
├── chat_controller.py         # Existing controller
├── config.py                  # Existing config
├── style.py                   # Existing style definitions
├── services/                  # API services (weather, calendar)
├── network/                   # Existing network code
├── audio/                     # Existing audio code
├── stt/                       # Existing STT code
├── wakeword/                  # Existing wake word code
└── ui/                        # Existing UI components
```

### Implementation Steps

1. **Create BaseWindow Class**
   - Extract common functionality from ChatWindow
   - Implement theme toggling, kiosk mode, and common UI elements
   - Define interface for screen-specific implementations

2. **Refactor ChatWindow**
   - Modify to inherit from BaseWindow
   - Keep chat-specific functionality
   - Ensure compatibility with window rotation

3. **Create Specialized Windows**
   - Implement ClockWindow with time/date display
   - Implement WeatherWindow with weather service integration
   - Implement CalendarWindow with calendar service integration
   - Implement PhotoWindow with photo slideshow functionality

4. **Develop WindowManager**
   - Create manager class to handle all windows
   - Implement screen rotation on timer
   - Add manual navigation controls
   - Synchronize theme and settings across windows

5. **Update Entry Point**
   - Modify client.py to use WindowManager
   - Ensure proper async event handling
   - Implement clean shutdown process

6. **Create Service Classes**
   - Implement WeatherService for API integration
   - Implement CalendarService for event fetching
   - Implement PhotoService for image management

## Technical Requirements
- **Platform**: Raspberry Pi (preferably Pi 4 or newer)
- **Display**: Compatible with various touchscreen displays
- **Framework**: PyQt6-based UI for performance and native look
- **Architecture**: Multiple windows approach with shared base components
- **Connectivity**: WiFi for accessing online services (weather, calendar)
- **Voice Interaction**: Support for wake word detection, STT, and TTS

## User Experience Goals
- **Clean Interface**: Minimalist design with good readability
- **Automatic Rotation**: Screens change automatically on a timer
- **Manual Navigation**: Touch or keyboard controls to manually switch screens
- **Kiosk Mode**: Fullscreen display without window decorations
- **Theme Support**: Light and dark themes for different environments
- **Accessibility**: Large text and high contrast options

## Integration Points
- **Weather API**: OpenWeather API for weather data
- **Calendar**: Google Calendar or local calendar integration
- **Photos**: Local photo directory and/or cloud photo services
- **AI Assistant**: Existing chat interface with STT/TTS capabilities

## Development Approach
- Leverage existing chat interface code
- Create a common base window class for shared functionality
- Implement specialized window classes for each screen type
- Develop a window manager to handle rotation and coordination
- Maintain consistent styling and behavior across all screens

## Future Expansion
- Additional information screens (news, stocks, home automation)
- Remote control via mobile app or web interface
- Multi-user support with personalized information
- Motion detection to activate display when someone approaches

This smart display will serve as a central information hub for the home, providing at-a-glance information and interactive capabilities in an elegant, unobtrusive package.

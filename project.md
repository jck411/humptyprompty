Smart Display Project Overview
Project Goal

Create a Raspberry Pi-based smart display that functions as a home information hub, showing various screens that rotate automatically. The display will show time, weather, calendar events, photos, and include a chat interface for interacting with an AI assistant.
Key Features

    Multi-screen Interface: Rotating display showing different information screens
    Clock Screen: Shows current time and date in a large, readable format
    Weather Screen: Displays current weather conditions and forecast
    Calendar Screen: Shows upcoming events from connected calendars
    Photo Screen: Displays a slideshow of photos from configured sources
    Chat Interface: Allows interaction with an AI assistant using text and voice

Technical Architecture
Architectural Recommendation: Single Window Pattern

For maximum stability on Raspberry Pi hardware and extended operation, the recommended architecture is:
Single Window with Content Stacking

    Core Concept: One persistent QMainWindow containing a QStackedWidget
    Benefits:
        No window creation/destruction during operation
        Complete control over transitions between content
        Very stable for long-running applications
        Lower memory footprint
        No window manager animations issues
        Better performance on Raspberry Pi hardware

Transition Animations

With this architecture, we can implement custom controlled transitions:

    Cross-fades using opacity effects on widgets
    Slide transitions using QPropertyAnimation
    Content morphing using Qt's animation framework
    Custom transition effects tailored to each screen type

Implementation Approach

    Create one persistent main window that initializes at startup
    Use QStackedWidget as the central widget to hold all "screens"
    Develop screen widgets inheriting from a common base class
    Create a view manager to handle screen transitions and animations
    Implement a timer-based rotation system for automatic transitions

Directory Structure

frontend/
├── __init__.py
├── client.py                  # Main entry point
├── main_window.py             # The single persistent window
├── base_screen.py             # Base class for all screen widgets
├── screen_manager.py          # Manages screen transitions and rotation
├── screens/
│   ├── __init__.py
│   ├── clock_screen.py        # Clock widget implementation
│   ├── chat_screen.py         # Chat interface widget 
│   ├── weather_screen.py      # Weather information widget
│   ├── calendar_screen.py     # Calendar events widget
│   └── photo_screen.py        # Photo slideshow widget
├── chat_controller.py         # Existing controller
├── config.py                  # Existing config
├── style.py                   # Existing style definitions
├── services/                  # API services (weather, calendar)
├── network/                   # Existing network code
├── audio/                     # Existing audio code
├── stt/                       # Existing STT code
├── wakeword/                  # Existing wake word code
└── ui/                        # Existing UI components

Implementation Steps

    Create MainWindow Class
        Persistent single window that hosts all content
        Implements fullscreen/kiosk mode
        Handles global keyboard shortcuts
        Sets up the QStackedWidget as central widget

    Create BaseScreen Class
        Defines common interface for all screen widgets
        Implements theme support
        Provides lifecycle methods (activate, deactivate)
        Handles transition animations

    Create Specialized Screens
        Implement ClockScreen with time/date display
        Implement ChatScreen for AI interaction
        Implement WeatherScreen with weather service integration
        Implement CalendarScreen with calendar service integration
        Implement PhotoScreen with photo slideshow functionality

    Develop ScreenManager
        Manages the QStackedWidget
        Implements screen rotation on timer
        Handles transition animations
        Synchronizes theme and settings across screens

    Update Entry Point
        Modify client.py to use the new architecture
        Ensure proper async event handling
        Implement clean shutdown process

    Create Service Classes
        Implement WeatherService for API integration
        Implement CalendarService for event fetching
        Implement PhotoService for image management

Technical Requirements

    Platform: Raspberry Pi (preferably Pi 4 or newer)
    Display: Compatible with various touchscreen displays
    Framework: PyQt6-based UI for performance and native look
    Architecture: Single window with multiple screens approach
    Connectivity: WiFi for accessing online services (weather, calendar)
    Voice Interaction: Support for wake word detection, STT, and TTS

User Experience Goals

    Clean Interface: Minimalist design with good readability
    Smooth Transitions: Custom animations between screens
    Automatic Rotation: Screens change automatically on a timer
    Manual Navigation: Touch or keyboard controls to manually switch screens
    Kiosk Mode: Fullscreen display without window decorations
    Theme Support: Light and dark themes for different environments
    Accessibility: Large text and high contrast options

Integration Points

    Weather API: OpenWeather API for weather data
    Calendar: Google Calendar or local calendar integration
    Photos: Local photo directory and/or cloud photo services
    AI Assistant: Existing chat interface with STT/TTS capabilities

Development Approach

    Create a solid main window foundation
    Implement the QStackedWidget-based content management
    Develop common base screen class for shared functionality
    Implement specialized screen classes for each content type
    Create beautiful, controlled transitions between screens
    Maintain consistent styling and behavior across all screens

Future Expansion

    Additional information screens (news, stocks, home automation)
    Remote control via mobile app or web interface
    Multi-user support with personalized information
    Motion detection to activate display when someone approaches

This smart display will serve as a central information hub for the home, providing at-a-glance information and interactive capabilities in an elegant, unobtrusive package.

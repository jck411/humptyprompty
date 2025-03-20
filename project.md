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
        - STT (Speech-to-Text) functionality with automatic timeout
        - Auto-send feature with visual countdown display
        - TTS (Text-to-Speech) for AI responses

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
├── config_manager.py          # Centralized configuration management
├── theme_manager.py           # Centralized theme management
├── error_handler.py           # Standardized error handling
├── chat_controller.py         # Chat functionality controller
├── config.py                  # Legacy config (being migrated to config_manager)
├── style.py                   # Legacy style definitions (being migrated to theme_manager)
├── network.py                 # Network communication
├── audio.py                   # Audio processing
├── screens/
│   ├── __init__.py
│   ├── clock_screen.py        # Clock widget implementation
│   ├── chat_screen.py         # Chat interface widget 
│   ├── weather_screen.py      # Weather information widget
│   ├── photos_screen.py       # Photo slideshow widget
│   └── settings_screen.py     # Settings configuration widget
├── ui/
│   ├── __init__.py
│   ├── chat_area.py           # Chat display area
│   ├── input_area.py          # User input area
│   ├── message_bubble.py      # Message display bubbles
│   ├── top_buttons.py         # Top control buttons
│   └── ...                    # Other UI components
├── stt/                       # Speech-to-text components
├── wakeword/                  # Wake word detection
└── icons/                     # UI icons and assets

Implementation Steps

    1. Core Framework
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

        Create ScreenManager
            Manages the QStackedWidget
            Implements screen rotation on timer
            Handles transition animations
            Synchronizes theme and settings across screens

    2. Foundation Components
        ErrorHandler Implementation
            Standardized exception classes for different error types
            Helper functions for consistent error logging
            Recovery mechanism utilities
            Decorator-based exception handling

        ConfigManager Implementation
            Hierarchical configuration with dot notation access
            Environment-specific configuration overrides
            Type-safe configuration access
            Configuration validation
            Environment variable support

        ThemeManager Implementation
            Centralized theme definitions
            Theme switching with signals
            Component-specific theme application
            Theme persistence between sessions
            Support for custom themes
            Stylesheet generation

    3. Specialized Screens
        Implement ClockScreen with time/date display
        Implement ChatScreen for AI interaction
        Implement WeatherScreen with weather service integration
        Implement PhotoScreen with photo slideshow functionality
        Implement SettingsScreen for configuration options

    4. Service Integration
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

Chat Interface Features

    STT (Speech-to-Text) Integration
        Wake word detection for hands-free activation
        Real-time transcription display
        Automatic timeout with visual countdown (15 seconds by default)
        Auto-send when silence detected

    TTS (Text-to-Speech) Integration
        High-quality voice synthesis for AI responses
        Toggle-able audio playback
        Support for multiple voices/languages

    Message Display
        User/AI message bubbles with clear visual distinction
        Typing indicators for AI responses
        Markdown/rich text support for AI responses
        Code block formatting and syntax highlighting

Development Approach

    Create a solid main window foundation
    Implement the QStackedWidget-based content management
    Develop common base screen class for shared functionality
    Implement specialized screen classes for each content type
    Create beautiful, controlled transitions between screens
    Maintain consistent styling and behavior across all screens
    Follow standardized coding patterns:
        - Centralized configuration management
        - Consistent error handling
        - Optimized imports
        - Consolidated theme management

Integration Points

    Weather API: OpenWeather API for weather data
    Calendar: Google Calendar or local calendar integration
    Photos: Local photo directory and/or cloud photo services
    AI Assistant: Existing chat interface with STT/TTS capabilities

Code Quality Improvements

    Import Optimization
        Organize imports into standard library, third-party, and local groups
        Sort imports alphabetically within each group
        Remove unused and duplicate imports
        Standardize import placement

    Error Handling
        Use standardized error_handler.py for consistent error management
        Implement error categorization and severity levels
        Provide appropriate user feedback based on error type
        Include retry mechanisms for network operations

    Configuration Management
        Migrate from direct config files to centralized config_manager.py
        Implement type-safe configuration access
        Support environment-specific settings
        Add validation for critical configuration values

    Theme Management
        Centralize theme definitions in theme_manager.py
        Implement consistent theme application across components
        Support theme customization and persistence
        Simplify theme switching with signals

Future Expansion

    Additional information screens (news, stocks, home automation)
    Remote control via mobile app or web interface
    Multi-user support with personalized information
    Motion detection to activate display when someone approaches

This smart display will serve as a central information hub for the home, providing at-a-glance information and interactive capabilities in an elegant, unobtrusive package.

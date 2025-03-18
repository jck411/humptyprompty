#!/usr/bin/env python3
"""
Screens module containing all screen implementations for the smart display.
"""

# Import all screens for easier access
from frontend.screens.clock_screen import ClockScreen
from frontend.screens.chat_screen import ChatScreen
from frontend.screens.weather_screen import WeatherScreen
from frontend.screens.calendar_screen import CalendarScreen
from frontend.screens.photo_screen import PhotoScreen

# List of all screen classes
__all__ = [
    'ClockScreen',
    'ChatScreen',
    'WeatherScreen',
    'CalendarScreen',
    'PhotoScreen'
] 
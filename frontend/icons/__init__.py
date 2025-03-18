#!/usr/bin/env python3
"""
Icons module for the smart display application.
Provides consistent access to application icons.
"""
import os
from PyQt6.QtGui import QIcon

# The directory containing this file
ICONS_DIR = os.path.dirname(os.path.abspath(__file__))

def get_icon(name, fallback=None):
    """
    Get an icon by name, with fallback to system theme icons
    
    Args:
        name: The name of the icon (without extension)
        fallback: The fallback icon name to use if the named icon is not found
    
    Returns:
        QIcon instance
    """
    # Try local application icon first
    icon_path = os.path.join(ICONS_DIR, f"{name}.png")
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    
    # Try system theme icon
    theme_icon = QIcon.fromTheme(name)
    if not theme_icon.isNull():
        return theme_icon
        
    # Try fallback
    if fallback:
        fallback_icon = QIcon.fromTheme(fallback)
        if not fallback_icon.isNull():
            return fallback_icon
    
    # Return empty icon as last resort
    return QIcon()

# Define common icons used in the application
ICON_CLOCK = lambda: get_icon("clock", "appointment-new")
ICON_CHAT = lambda: get_icon("chat", "internet-chat")
ICON_WEATHER = lambda: get_icon("weather", "weather-few-clouds")
ICON_CALENDAR = lambda: get_icon("calendar", "office-calendar")
ICON_PHOTO = lambda: get_icon("photo", "image-x-generic")
ICON_SETTINGS = lambda: get_icon("settings", "preferences-system")
ICON_THEME = lambda: get_icon("theme", "preferences-desktop-color")
ICON_RETURN = lambda: get_icon("return", "go-previous") 
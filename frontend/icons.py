from PyQt6.QtGui import QIcon
import os
from pathlib import Path

# Define the icons directory path
ICONS_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "icons"

# Dictionary mapping icon names to their QIcon objects
ICONS = {
    # Navigation and window controls
    'chat': QIcon(str(ICONS_DIR / "chat.svg")),
    'clock': QIcon(str(ICONS_DIR / "clock.svg")),
    'fullscreen': QIcon(str(ICONS_DIR / "fullscreen.svg")),
    'fullscreen_exit': QIcon(str(ICONS_DIR / "fullscreen_exit.svg")),
    
    # Audio controls
    'mic': QIcon(str(ICONS_DIR / "mic.svg")),
    'sound_on': QIcon(str(ICONS_DIR / "sound_on.svg")),
    'sound_off': QIcon(str(ICONS_DIR / "sound_off.svg")),
    
    # Action buttons
    'send': QIcon(str(ICONS_DIR / "send.svg")),
    'stop_all': QIcon(str(ICONS_DIR / "stop_all.svg")),
    'stop_circle': QIcon(str(ICONS_DIR / "stop_circle.svg")),
    'clear_all': QIcon(str(ICONS_DIR / "clear_all.svg")),
    
    # Theme controls
    'theme': QIcon(str(ICONS_DIR / "theme.svg")),
    'light_mode': QIcon(str(ICONS_DIR / "light_mode.svg")),
    'dark_mode': QIcon(str(ICONS_DIR / "dark_mode.svg"))
}

def get_icon(name):
    """
    Retrieve an icon by name from the centralized icons dictionary.
    
    Args:
        name (str): The name of the icon to retrieve.
        
    Returns:
        QIcon: The requested icon, or an empty QIcon if not found.
    """
    return ICONS.get(name, QIcon()) 
# style.py
# Consolidated styling and appearance module
import os

DARK_COLORS = {
    "background": "#1a1b26", 
    "user_bubble": "#3b4261", 
    "assistant_bubble": "transparent", 
    "text_primary": "#a9b1d6", 
    "text_secondary": "#565f89", 
    "button_primary": "#7aa2f7", 
    "button_hover": "#3d59a1", 
    "button_pressed": "#2ac3de", 
    "input_background": "#24283b", 
    "input_border": "#414868"
}

LIGHT_COLORS = {
    "background": "#E8EEF5",
    "user_bubble": "#D0D7E1", 
    "assistant_bubble": "#F7F9FB", 
    "text_primary": "#1C1E21", 
    "text_secondary": "#65676B", 
    "button_primary": "#0D8BD9", 
    "button_hover": "#0A6CA8", 
    "button_pressed": "#084E7A", 
    "input_background": "#FFFFFF", 
    "input_border": "#D3D7DC"
}

def load_stylesheet(is_dark_mode):
    """
    Load the appropriate stylesheet based on the current theme.
    
    Args:
        is_dark_mode (bool): True for dark mode, False for light mode
        
    Returns:
        str: The stylesheet content
    """
    theme = 'dark' if is_dark_mode else 'light'
    stylesheet_path = os.path.join(os.path.dirname(__file__), 'styles', f'{theme}.qss')
    
    try:
        with open(stylesheet_path, 'r') as file:
            stylesheet = file.read()
        return stylesheet
    except FileNotFoundError:
        print(f"Stylesheet file not found: {stylesheet_path}")
        return ""

# Kept for backward compatibility, redirects to load_stylesheet
def generate_main_stylesheet(colors):
    """
    Legacy function that now loads the stylesheet from files.
    Kept for backward compatibility.
    
    Args:
        colors (dict): Dictionary of colors for the current theme (unused)
        
    Returns:
        str: The stylesheet content
    """
    is_dark_mode = colors == DARK_COLORS
    return load_stylesheet(is_dark_mode)

# Kept for backward compatibility, will be handled by QSS files
def get_message_bubble_stylesheet(is_user, colors):
    """
    Legacy function for getting message bubble styles.
    This is now handled by the QSS files.
    
    Args:
        is_user (bool): Whether this is a user message bubble
        colors (dict): Dictionary of colors for the current theme
        
    Returns:
        str: Empty string as styles are now in QSS files
    """
    return ""


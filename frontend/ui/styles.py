"""
UI styling utilities for the frontend application.
"""
from frontend.config.config import UI_CONFIG

def generate_main_stylesheet(colors):
    """
    Generate the main application stylesheet based on the provided colors.
    
    Args:
        colors: Dictionary of color values.
        
    Returns:
        A CSS stylesheet string.
    """
    return f"""
    QWidget {{
        font-family: {UI_CONFIG['font_family']};
        background-color: {colors['background']};
    }}
    QMainWindow {{
        background-color: {colors['background']};
    }}
    QScrollArea {{
        border: none;
        background-color: {colors['background']};
    }}
    QScrollBar:vertical {{
        border: none;
        background: {colors['background']};
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {colors['input_border']};
        border-radius: 5px;
        min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
        width: 0;
        background: none;
        border: none;
    }}
    QTextEdit {{
        border: 1px solid {colors['input_border']};
        border-radius: 20px;
        padding: 10px;
        background-color: {colors['input_background']};
        color: {colors['text_primary']};
        font-size: {UI_CONFIG['font_size']['normal']}px;
    }}
    QPushButton {{
        border: none;
        border-radius: 25px;
        background-color: {colors['button_primary']};
        color: white;
        padding: 5px;
        font-weight: bold;
        font-size: {UI_CONFIG['font_size']['button']}px;
    }}
    QPushButton:hover {{
        background-color: {colors['button_hover']};
    }}
    QPushButton:pressed {{
        background-color: {colors['button_pressed']};
    }}
    QLabel {{
        color: {colors['text_primary']};
        font-size: {UI_CONFIG['font_size']['normal']}px;
    }}
    QPushButton#sttButton[isListening="true"] {{
        background-color: red !important;
        color: white !important;
        border: none;
        border-radius: 10px;
    }}
    """

def get_message_bubble_stylesheet(is_user, colors):
    """
    Generate the stylesheet for message bubbles.
    
    Args:
        is_user: Boolean indicating if the message is from the user.
        colors: Dictionary of color values.
        
    Returns:
        A CSS stylesheet string.
    """
    if is_user:
        return f"""
            QFrame#messageBubble {{
                background-color: {colors['user_bubble']};
                border-radius: 15px;
                margin: 5px 50px 5px 5px;
                padding: 5px;
            }}
            QLabel {{
                color: {colors['text_primary']};
                font-size: {UI_CONFIG['font_size']['normal']}px;
                background-color: transparent;
            }}
        """
    else:
        return f"""
            QFrame#messageBubble {{
                background-color: transparent;
                margin: 5px 5px 5px 50px;
                padding: 5px;
            }}
            QLabel {{
                color: {colors['text_primary']};
                font-size: {UI_CONFIG['font_size']['normal']}px;
                background-color: transparent;
            }}
        """

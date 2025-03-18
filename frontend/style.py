# style.py
# Consolidated styling and appearance module

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

def generate_main_stylesheet(colors):
    return f"""
    /* Base styling for all widgets */
    QWidget {{
        font-family: 'DejaVu Sans', 'sans-serif';
        background-color: {colors['background']};
    }}
    
    QMainWindow {{
        background-color: {colors['background']};
    }}
    
    /* Scrollbars */
    QScrollArea {{
        border: none;
        background-color: {colors['background']};
    }}
    
    QScrollBar:vertical {{
        border: none;
        background: {colors['background']};
        width: 14px;  /* Wider for touch */
        margin: 0;
    }}
    
    QScrollBar::handle:vertical {{
        background: {colors['input_border']};
        border-radius: 7px;
        min-height: 40px;  /* Easier to grab */
    }}
    
    /* Typography */
    QLabel {{
        color: {colors['text_primary']};
        font-size: 16px;  /* Larger for readability */
    }}
    
    QLabel[title="true"] {{
        font-size: 24px;
        font-weight: bold;
    }}
    
    /* Buttons */
    QPushButton {{
        background-color: {colors['button_primary']};
        color: white;
        border: none;
        padding: 14px;  /* Larger for touch */
        border-radius: 8px;
        font-size: 16px;
        min-height: 48px;
    }}
    
    QPushButton:hover {{
        background-color: {colors['button_hover']};
    }}
    
    QPushButton:pressed {{
        background-color: {colors['button_pressed']};
    }}
    
    /* Input elements */
    QLineEdit, QTextEdit {{
        background-color: {colors['input_background']};
        color: {colors['text_primary']};
        border: 1px solid {colors['input_border']};
        border-radius: 8px;
        padding: 10px;
        font-size: 16px;
    }}
    
    QLineEdit:focus, QTextEdit:focus {{
        border: 2px solid {colors['button_primary']};
    }}
    
    /* Kiosk-specific styling */
    QStackedWidget {{
        background-color: {colors['background']};
    }}
    
    /* Navigation bar styling */
    #nav_bar {{
        background-color: {colors['input_background']};
        border-bottom: 2px solid {colors['input_border']};
        min-height: 70px;
    }}
    
    #nav_bar QLabel {{
        font-size: 22px;
        font-weight: bold;
        color: {colors['text_primary']};
    }}
    
    #nav_bar QPushButton {{
        background-color: transparent;
        border-radius: 24px;
        min-width: 56px;
        min-height: 56px;
        icon-size: 30px;
        padding: 12px;
        margin: 0 4px;
    }}
    
    #nav_bar QPushButton:hover {{
        background-color: {colors['button_hover']};
    }}
    
    #nav_bar QPushButton[current="true"] {{
        background-color: {colors['button_primary']};
    }}
    """

def get_message_bubble_stylesheet(is_user, colors):
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
                font-size: 14px;
                background-color: transparent;
            }}
        """
    else:
        return f"""
            QFrame#messageBubble {{
                background-color: {colors['assistant_bubble']};
                margin: 5px 5px 5px 50px;
                padding: 5px;
            }}
            QLabel {{
                color: {colors['text_primary']};
                font-size: 14px;
                background-color: transparent;
            }}
        """


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
    QWidget {{
        font-family: 'DejaVu Sans', 'sans-serif';
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
        font-size: 14px;
    }}
    QPushButton {{
        border: none;
        border-radius: 25px;
        background-color: {colors['button_primary']};
        color: white;
        padding: 5px;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: {colors['button_hover']};
    }}
    QPushButton:pressed {{
        background-color: {colors['button_pressed']};
    }}
    QLabel {{
        color: {colors['text_primary']};
        font-size: 14px;
    }}
    QPushButton#sttButton[isEnabled="true"][isListening="false"] {{
        background-color: green !important;
        color: white !important;
        border: none;
        border-radius: 10px;
    }}
    QPushButton#sttButton[isListening="true"] {{
        background-color: red !important;
        color: white !important;
        border: none;
        border-radius: 10px;
    }}
    QPushButton#autoSendButton[isAutoSend="true"] {{
        background-color: green !important;
        color: white !important;
        border: none;
        border-radius: 10px;
    }}
    QPushButton#ttsButton[isTtsEnabled="true"] {{
        background-color: green !important;
        color: white !important;
        border: none;
        border-radius: 10px;
    }}
    """

def get_message_bubble_stylesheet(is_user, colors, is_transcription=False):
    """Get the stylesheet for message bubbles based on the current theme"""
    user_bg_color = colors['user_bubble']
    assistant_bg_color = colors['assistant_bubble']
    user_text_color = colors['text_primary']
    assistant_text_color = colors['text_primary']
    
    # For transcriptions, use a lighter/more transparent background
    if is_transcription:
        # Create a more transparent version for transcriptions
        # This assumes the color is a hex color like "#rrggbb"
        if user_bg_color.startswith('#') and len(user_bg_color) == 7:
            r = int(user_bg_color[1:3], 16)
            g = int(user_bg_color[3:5], 16)
            b = int(user_bg_color[5:7], 16)
            user_bg_color = f"rgba({r}, {g}, {b}, 0.6)"
    
    if is_user:
        return f"""
        QWidget {{
            background-color: {user_bg_color};
            border-radius: 18px;
            margin-left: 60px;
            margin-right: 10px;
        }}
        QLabel {{
            color: {user_text_color};
            background-color: transparent;
            padding: 10px 15px;
            font-size: 16px;
            qproperty-wordWrap: true;
        }}
        """
    else:
        return f"""
        QWidget {{
            background-color: {assistant_bg_color};
            border-radius: 18px;
            margin-left: 10px;
            margin-right: 60px;
        }}
        QLabel {{
            color: {assistant_text_color};
            background-color: transparent;
            padding: 10px 15px;
            font-size: 16px;
            qproperty-wordWrap: true;
        }}
        """


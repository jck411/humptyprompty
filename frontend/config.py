import logging

# Server Configuration
SERVER_HOST = "192.168.1.226"  # <-- CHANGE THIS to your server's local IP
SERVER_PORT = 8000
WEBSOCKET_PATH = "/ws/chat"
HTTP_BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# Color Schemes
LIGHT_COLORS = {
    'background': '#FFFFFF',
    'user_bubble': '#F2F2F2',
    'assistant_bubble': '#E8E8E8',
    'text_primary': '#000000',
    'text_secondary': '#666666',
    'button_primary': '#0D8BD9',
    'button_hover': '#0A6CA8',
    'button_pressed': '#084E7A',
    'input_background': '#FFFFFF',
    'input_border': '#E0E0E0'
}

DARK_COLORS = {
    'background': '#2D2D2D',
    'user_bubble': '#202020',
    'assistant_bubble': '#2D2D2D',
    'text_primary': '#E8EAED',
    'text_secondary': '#9AA0A6',
    'button_primary': '#0D8BD9',
    'button_hover': '#0A6CA8',
    'button_pressed': '#084E7A',
    'input_background': '#2D2D2D',
    'input_border': '#404040'
}

# Icon colors
ICON_DARK_MODE = '#0D8BD9'
ICON_LIGHT_MODE = '#E8EAED'

# Default to light theme
COLORS = LIGHT_COLORS.copy()

# Logging Configuration
LOG_LEVEL = logging.WARNING
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)
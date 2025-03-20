#!/usr/bin/env python3
import logging
import os
from typing import Dict, Any, Optional

# -----------------------------------------------------------------------------
#                           SERVER CONFIGURATION
# -----------------------------------------------------------------------------

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
WEBSOCKET_PATH = "/ws/chat"
HTTP_BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# -----------------------------------------------------------------------------
#                           APPLICATION CONFIGURATION
# -----------------------------------------------------------------------------

# Default application settings
APP_CONFIG: Dict[str, Any] = {
    'theme': 'dark',
    'auto_rotate': True,
    'rotation_interval': 30000,  # 30 seconds
    'default_screen': 'chat',
    'fullscreen': True,
    'debug_mode': False
}

# -----------------------------------------------------------------------------
#                           LOGGING CONFIGURATION
# -----------------------------------------------------------------------------

# Default log level - can be overridden by environment variable
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

def setup_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Configure and return a logger with the specified name and level.
    
    Args:
        name: The name for the logger
        level: The logging level (default: level from LOG_LEVEL env var or INFO)
        
    Returns:
        A configured logger instance
    """
    # Set up basic logging if not already configured
    if not logging.root.handlers:
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL),
            format=LOG_FORMAT
        )
    
    # Get or create logger
    logger = logging.getLogger(name)
    
    # Set level if provided
    if level is not None:
        logger.setLevel(level)
    
    return logger

# Default logger instance for the config module
logger = setup_logger('config', getattr(logging, LOG_LEVEL))

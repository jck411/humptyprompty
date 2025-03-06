#!/usr/bin/env python3
import logging

# -----------------------------------------------------------------------------
#                           SERVER CONFIGURATION
# -----------------------------------------------------------------------------

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
WEBSOCKET_PATH = "/ws/chat"
HTTP_BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# -----------------------------------------------------------------------------
#                           LOGGING CONFIGURATION
# -----------------------------------------------------------------------------

def setup_logger(name=__name__, level=logging.WARNING):
    """
    Configure and return a logger with the specified name and level.
    
    Args:
        name: The name for the logger (default: module name)
        level: The logging level (default: WARNING)
        
    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create console handler with formatter
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(formatter)
    
    # Add handler to logger if not already added
    if not logger.handlers:
        logger.addHandler(ch)
        
    return logger

# Default logger instance
logger = setup_logger() 
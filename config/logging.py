# config/logging.py

from typing import Optional
from .config import CONFIG

def conditional_print(message: str, print_type: str = "default") -> None:
    """
    Print messages based on configuration settings.
    
    Args:
        message (str): The message to print
        print_type (str): Type of message ('segment', 'tool_call', 'function_call', or 'default')
    """
    if print_type == "segment" and CONFIG["LOGGING"]["PRINT_SEGMENTS"]:
        print(f"[SEGMENT] {message}")
    elif print_type == "tool_call" and CONFIG["LOGGING"]["PRINT_TOOL_CALLS"]:
        print(f"[TOOL CALL] {message}")
    elif print_type == "function_call" and CONFIG["LOGGING"]["PRINT_FUNCTION_CALLS"]:
        print(f"[FUNCTION CALL] {message}")
    elif CONFIG["LOGGING"]["PRINT_ENABLED"]:
        print(f"[INFO] {message}")

# You could add more logging functions here in the future, for example:
def log_error(message: str, error: Optional[Exception] = None) -> None:
    """Log error messages with optional exception details."""
    error_msg = f"[ERROR] {message}"
    if error:
        error_msg += f": {str(error)}"
    print(error_msg)

def log_startup(message: str) -> None:
    """Log startup-related messages."""
    print(f"[STARTUP] {message}")

def log_shutdown(message: str) -> None:
    """Log shutdown-related messages."""
    print(f"[SHUTDOWN] {message}")

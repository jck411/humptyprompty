#!/usr/bin/env python3
"""
Standardized error handling module for the application.
This module provides consistent error handling, logging, and recovery mechanisms.
"""
import logging
import traceback
import asyncio
import time
from enum import Enum
from typing import Callable, Optional, Any, Dict, Type, Union

# Configure logger
logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Enum defining error severity levels"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

class ErrorCategory(Enum):
    """Enum defining error categories for better organization"""
    NETWORK = "network"
    AUDIO = "audio"
    STT = "speech_to_text"
    TTS = "text_to_speech"
    UI = "user_interface"
    CONFIG = "configuration"
    WAKEWORD = "wake_word"
    GENERAL = "general"

class AppError(Exception):
    """Base exception class for application-specific errors"""
    def __init__(
        self, 
        message: str, 
        category: ErrorCategory = ErrorCategory.GENERAL,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.original_exception = original_exception
        self.context = context or {}
        self.traceback = traceback.format_exc() if original_exception else None
        
        # Call the base class constructor
        super().__init__(message)
    
    def __str__(self) -> str:
        """String representation of the error"""
        result = f"{self.category.value.upper()} ERROR: {self.message}"
        if self.original_exception:
            result += f" (Original error: {str(self.original_exception)})"
        return result

# Specific error types
class NetworkError(AppError):
    """Network-related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.NETWORK, **kwargs)

class AudioError(AppError):
    """Audio-related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.AUDIO, **kwargs)

class STTError(AppError):
    """Speech-to-text related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.STT, **kwargs)

class TTSError(AppError):
    """Text-to-speech related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.TTS, **kwargs)

class UIError(AppError):
    """UI-related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.UI, **kwargs)

class ConfigError(AppError):
    """Configuration-related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.CONFIG, **kwargs)

class WakeWordError(AppError):
    """Wake word detection related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.WAKEWORD, **kwargs)

# Error handling functions
def log_error(error: Union[AppError, Exception], log_traceback: bool = True) -> None:
    """
    Log an error with the appropriate severity level
    
    Args:
        error: The error to log
        log_traceback: Whether to include the traceback in the log
    """
    if isinstance(error, AppError):
        # Use the severity from the AppError
        if error.severity == ErrorSeverity.DEBUG:
            logger.debug(str(error))
        elif error.severity == ErrorSeverity.INFO:
            logger.info(str(error))
        elif error.severity == ErrorSeverity.WARNING:
            logger.warning(str(error))
        elif error.severity == ErrorSeverity.CRITICAL:
            logger.critical(str(error))
        else:  # Default to ERROR
            logger.error(str(error))
            
        # Log traceback if available and requested
        if log_traceback and error.traceback:
            logger.debug(f"Traceback for {error.category.value} error:\n{error.traceback}")
            
        # Log additional context if available
        if error.context:
            logger.debug(f"Error context: {error.context}")
    else:
        # For standard exceptions, log as error with traceback
        logger.error(str(error))
        if log_traceback:
            logger.debug(f"Traceback:\n{traceback.format_exc()}")

def handle_exception(
    error_type: Type[AppError] = AppError,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    log_error: bool = True,
    reraise: bool = False
) -> Callable:
    """
    Decorator for exception handling in functions
    
    Args:
        error_type: The type of AppError to wrap the exception in
        severity: The severity level for the error
        log_error: Whether to log the error
        reraise: Whether to reraise the wrapped exception
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Skip wrapping if it's already an AppError
                if isinstance(e, AppError):
                    app_error = e
                else:
                    # Create a new AppError with the original exception
                    app_error = error_type(
                        f"Error in {func.__name__}: {str(e)}",
                        severity=severity,
                        original_exception=e
                    )
                
                # Log the error if requested
                if log_error:
                    log_error(app_error)
                
                # Reraise if requested
                if reraise:
                    raise app_error
                
                # Return None if not reraising
                return None
        
        # Handle async functions
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # Skip wrapping if it's already an AppError
                    if isinstance(e, AppError):
                        app_error = e
                    else:
                        # Create a new AppError with the original exception
                        app_error = error_type(
                            f"Error in async {func.__name__}: {str(e)}",
                            severity=severity,
                            original_exception=e
                        )
                    
                    # Log the error if requested
                    if log_error:
                        log_error(app_error)
                    
                    # Reraise if requested
                    if reraise:
                        raise app_error
                    
                    # Return None if not reraising
                    return None
            
            return async_wrapper
        
        return wrapper
    
    return decorator

# Recovery mechanisms
async def retry_async_operation(
    operation: Callable,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    error_types: tuple = (Exception,),
    *args, **kwargs
) -> Any:
    """
    Retry an async operation with exponential backoff
    
    Args:
        operation: The async function to retry
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        backoff_factor: Factor to increase delay with each retry
        error_types: Tuple of exception types to catch and retry
        *args, **kwargs: Arguments to pass to the operation
        
    Returns:
        Result of the operation if successful
        
    Raises:
        Last exception encountered if all retries fail
    """
    retries = 0
    current_delay = retry_delay
    
    while True:
        try:
            return await operation(*args, **kwargs)
        except error_types as e:
            retries += 1
            if retries >= max_retries:
                logger.error(f"Operation failed after {max_retries} retries: {str(e)}")
                raise
            
            logger.warning(f"Retry {retries}/{max_retries} after error: {str(e)}")
            logger.warning(f"Waiting {current_delay:.2f} seconds before retry")
            
            await asyncio.sleep(current_delay)
            current_delay *= backoff_factor

def retry_operation(
    operation: Callable,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    error_types: tuple = (Exception,),
    *args, **kwargs
) -> Any:
    """
    Retry a synchronous operation with exponential backoff
    
    Args:
        operation: The function to retry
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        backoff_factor: Factor to increase delay with each retry
        error_types: Tuple of exception types to catch and retry
        *args, **kwargs: Arguments to pass to the operation
        
    Returns:
        Result of the operation if successful
        
    Raises:
        Last exception encountered if all retries fail
    """
    retries = 0
    current_delay = retry_delay
    
    while True:
        try:
            return operation(*args, **kwargs)
        except error_types as e:
            retries += 1
            if retries >= max_retries:
                logger.error(f"Operation failed after {max_retries} retries: {str(e)}")
                raise
            
            logger.warning(f"Retry {retries}/{max_retries} after error: {str(e)}")
            logger.warning(f"Waiting {current_delay:.2f} seconds before retry")
            
            time.sleep(current_delay)
            current_delay *= backoff_factor

# Usage examples:
"""
# Example 1: Using the error handling decorator
@handle_exception(error_type=NetworkError, severity=ErrorSeverity.WARNING)
def fetch_data(url):
    # Implementation...
    pass

# Example 2: Using the retry mechanism
async def get_weather_data(city):
    async def _fetch_weather(city):
        # Implementation that might fail...
        pass
    
    try:
        return await retry_async_operation(
            _fetch_weather,
            max_retries=3,
            error_types=(NetworkError, TimeoutError),
            city=city
        )
    except Exception as e:
        log_error(NetworkError("Failed to fetch weather data", original_exception=e))
        return None

# Example 3: Direct error handling
try:
    # Some operation that might fail
    pass
except Exception as e:
    error = AudioError(
        "Failed to initialize audio device",
        severity=ErrorSeverity.CRITICAL,
        original_exception=e,
        context={"device_name": "default"}
    )
    log_error(error)
    # Recovery logic...
"""

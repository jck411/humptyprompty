"""
Logging utility for the frontend application.
"""
import logging
import sys
import os
from typing import Optional
from frontend.config.config import LOG_CONFIG

class Logger:
    """
    Logger utility class for the frontend application.
    Provides a centralized way to configure and access loggers.
    """
    _initialized = False
    _loggers = {}

    @classmethod
    def initialize(cls, config=None):
        """
        Initialize the logging system with the given configuration.
        
        Args:
            config: Optional configuration dictionary. If None, uses LOG_CONFIG from config.py.
        """
        if cls._initialized:
            return
        
        if config is None:
            config = LOG_CONFIG
        
        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(config.get('level', logging.INFO))
        
        # Create formatter
        formatter = logging.Formatter(
            config.get('format', "%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
            config.get('date_format', "%Y-%m-%d %H:%M:%S")
        )
        
        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Add file handler if specified
        log_file = config.get('file')
        if log_file:
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        cls._initialized = True
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a logger with the given name.
        
        Args:
            name: The name of the logger.
            
        Returns:
            A configured logger instance.
        """
        if not cls._initialized:
            cls.initialize()
        
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        
        return cls._loggers[name]

# Initialize logging on module import
Logger.initialize()

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.
    
    Args:
        name: The name of the logger.
        
    Returns:
        A configured logger instance.
    """
    return Logger.get_logger(name)

#!/usr/bin/env python3
"""
Unified configuration management system for the application.
This module provides a centralized way to access configuration settings
with support for hierarchical configuration, validation, and environment-specific settings.
"""
import os
import json
import logging
from typing import Any, Dict, Optional, Union, List, Callable, TypeVar, cast
from pathlib import Path
from enum import Enum

# Configure logger
logger = logging.getLogger(__name__)

# Type definitions
T = TypeVar('T')
ConfigValue = Union[str, int, float, bool, List[Any], Dict[str, Any], None]
ValidationFunction = Callable[[Any], bool]

class ConfigEnvironment(Enum):
    """Enum defining configuration environments"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"

class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails"""
    pass

class ConfigManager:
    """
    Centralized configuration manager that provides access to all application settings.
    
    Features:
    - Hierarchical configuration with dot notation access
    - Environment-specific configuration overrides
    - Configuration validation
    - Default values for missing settings
    - Environment variable overrides
    """
    
    def __init__(self):
        """Initialize the configuration manager"""
        self._config: Dict[str, Any] = {}
        self._validators: Dict[str, ValidationFunction] = {}
        self._environment = self._detect_environment()
        self._loaded = False
        
    def _detect_environment(self) -> ConfigEnvironment:
        """Detect the current environment based on environment variables"""
        env = os.environ.get("APP_ENV", "development").lower()
        if env == "production":
            return ConfigEnvironment.PRODUCTION
        elif env == "test":
            return ConfigEnvironment.TEST
        else:
            return ConfigEnvironment.DEVELOPMENT
    
    def load_config(self, config_dir: Optional[str] = None) -> None:
        """
        Load configuration from files
        
        Args:
            config_dir: Directory containing configuration files (default.py, development.py, etc.)
                        If None, uses the default config directory
        """
        if self._loaded:
            logger.warning("Configuration already loaded, use reload_config() to reload")
            return
            
        if config_dir is None:
            # Use default config directory (assuming it's in the project root)
            config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        
        # Load default configuration
        default_config = self._load_config_file(os.path.join(config_dir, "default.py"))
        if not default_config:
            logger.warning("No default configuration found, starting with empty configuration")
            default_config = {}
        
        # Load environment-specific configuration
        env_config_file = os.path.join(config_dir, f"{self._environment.value}.py")
        env_config = self._load_config_file(env_config_file)
        
        # Merge configurations
        self._config = self._deep_merge(default_config, env_config or {})
        
        # Override with environment variables
        self._override_from_env()
        
        self._loaded = True
        logger.info(f"Configuration loaded for environment: {self._environment.value}")
    
    def _load_config_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Load configuration from a Python file
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            Dictionary with configuration values or None if file not found
        """
        try:
            # For Python files, we'll use exec to load them as modules
            if file_path.endswith('.py'):
                config_vars: Dict[str, Any] = {}
                with open(file_path, 'r') as f:
                    # Execute the file content in a controlled namespace
                    exec(f.read(), {}, config_vars)
                
                # Remove any special variables (like __builtins__)
                return {k: v for k, v in config_vars.items() 
                        if not k.startswith('__') and not k.endswith('__')}
            
            # For JSON files
            elif file_path.endswith('.json'):
                with open(file_path, 'r') as f:
                    return json.load(f)
                    
            # Unsupported file type
            else:
                logger.error(f"Unsupported configuration file type: {file_path}")
                return None
                
        except FileNotFoundError:
            logger.debug(f"Configuration file not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error loading configuration file {file_path}: {e}")
            return None
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries, with override values taking precedence
        
        Args:
            base: Base dictionary
            override: Dictionary with override values
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            # If both values are dictionaries, merge them recursively
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                # Otherwise, override the value
                result[key] = value
                
        return result
    
    def _override_from_env(self) -> None:
        """Override configuration values from environment variables"""
        # Look for environment variables with the APP_ prefix
        for key, value in os.environ.items():
            if key.startswith("APP_"):
                # Convert APP_SECTION_KEY to section.key
                config_key = key[4:].lower().replace("_", ".")
                
                # Convert value to appropriate type
                typed_value = self._convert_env_value(value)
                
                # Set the configuration value
                self.set(config_key, typed_value)
    
    def _convert_env_value(self, value: str) -> ConfigValue:
        """
        Convert environment variable string value to appropriate type
        
        Args:
            value: String value from environment variable
            
        Returns:
            Converted value with appropriate type
        """
        # Try to convert to boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        elif value.lower() in ("false", "no", "0"):
            return False
            
        # Try to convert to number
        try:
            if "." in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            # If conversion fails, keep as string
            pass
            
        # Try to convert to JSON
        if value.startswith("{") or value.startswith("["):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
                
        # Default to string
        return value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value
        
        Args:
            key: Configuration key in dot notation (e.g., "audio.tts.enabled")
            default: Default value if key is not found
            
        Returns:
            Configuration value or default if not found
        """
        if not self._loaded:
            logger.warning("Configuration not loaded, returning default value")
            return default
            
        # Split the key into parts
        parts = key.split(".")
        
        # Navigate through the configuration dictionary
        current = self._config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
                
        return current
    
    def get_typed(self, key: str, default: T, expected_type: type) -> T:
        """
        Get a configuration value with type checking
        
        Args:
            key: Configuration key in dot notation
            default: Default value if key is not found
            expected_type: Expected type of the value
            
        Returns:
            Configuration value or default if not found
            
        Raises:
            ConfigValidationError: If the value is not of the expected type
        """
        value = self.get(key, default)
        
        # Check if the value is of the expected type
        if value is not None and not isinstance(value, expected_type):
            raise ConfigValidationError(
                f"Configuration value for '{key}' is not of expected type {expected_type.__name__}"
            )
            
        return cast(T, value)
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer configuration value"""
        return self.get_typed(key, default, int)
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a float configuration value"""
        return self.get_typed(key, default, float)
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value"""
        return self.get_typed(key, default, bool)
    
    def get_str(self, key: str, default: str = "") -> str:
        """Get a string configuration value"""
        return self.get_typed(key, default, str)
    
    def get_list(self, key: str, default: Optional[List[Any]] = None) -> List[Any]:
        """Get a list configuration value"""
        if default is None:
            default = []
        return self.get_typed(key, default, list)
    
    def get_dict(self, key: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get a dictionary configuration value"""
        if default is None:
            default = {}
        return self.get_typed(key, default, dict)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value
        
        Args:
            key: Configuration key in dot notation
            value: Value to set
        """
        # Split the key into parts
        parts = key.split(".")
        
        # Navigate through the configuration dictionary
        current = self._config
        for i, part in enumerate(parts[:-1]):
            # Create nested dictionaries if they don't exist
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
            
        # Set the value
        current[parts[-1]] = value
        
        # Validate the value if a validator exists
        if key in self._validators:
            if not self._validators[key](value):
                logger.warning(f"Validation failed for configuration key '{key}'")
    
    def register_validator(self, key: str, validator: ValidationFunction) -> None:
        """
        Register a validation function for a configuration key
        
        Args:
            key: Configuration key in dot notation
            validator: Function that takes a value and returns True if valid, False otherwise
        """
        self._validators[key] = validator
        
        # Validate existing value if it exists
        if self._loaded:
            value = self.get(key)
            if value is not None and not validator(value):
                logger.warning(f"Validation failed for existing configuration key '{key}'")
    
    def reload_config(self) -> None:
        """Reload configuration from files"""
        self._loaded = False
        self.load_config()
    
    def get_all(self) -> Dict[str, Any]:
        """Get a copy of the entire configuration dictionary"""
        return self._config.copy()
    
    def get_environment(self) -> ConfigEnvironment:
        """Get the current configuration environment"""
        return self._environment
    
    def set_environment(self, environment: ConfigEnvironment) -> None:
        """
        Set the configuration environment and reload configuration
        
        Args:
            environment: New environment to use
        """
        self._environment = environment
        self.reload_config()

# Create a singleton instance
config = ConfigManager()

# Example usage:
"""
# Load configuration
config.load_config()

# Access configuration values
debug_mode = config.get_bool("app.debug", False)
server_port = config.get_int("server.port", 8080)
api_url = config.get_str("api.url", "http://localhost:8000")

# Register validators
config.register_validator("server.port", lambda x: isinstance(x, int) and 1024 <= x <= 65535)
config.register_validator("api.url", lambda x: isinstance(x, str) and x.startswith("http"))

# Set configuration values
config.set("logging.level", "DEBUG")
"""

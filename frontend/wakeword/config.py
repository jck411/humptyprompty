#!/usr/bin/env python3
"""
Wake word detection configuration settings
"""
import os
from pathlib import Path

# Path to the wake word model files
WAKEWORD_DIR = Path(__file__).parent
MODELS_DIR = WAKEWORD_DIR / "models"

# Create models directory if it doesn't exist
os.makedirs(MODELS_DIR, exist_ok=True)

# Wake word configuration
WAKEWORD_CONFIG = {
    # Enable/disable wake word detection
    'enabled': True,
    
    # Sensitivity (higher = more sensitive, lower = fewer false positives)
    'sensitivity': 0.7,
    
    # Wake word to use
    'model_path': str(MODELS_DIR / "computer_en_linux_v3_0_0.ppn"),
    
    # Audio settings
    'sample_rate': 16000,
    'audio_device_index': None,  # None = default device
    
    # Cooldown period between wake word detections (in seconds)
    'cooldown_period': 3.0,
    
    # Auto start wake word detection on application start
    'auto_start': True,
} 
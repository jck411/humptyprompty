#!/usr/bin/env python3
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

from frontend.base_screen import BaseScreen
from frontend.config import logger

class WeatherScreen(BaseScreen):
    """
    Screen that displays weather information.
    Placeholder for future implementation.
    """
    def __init__(self, colors):
        """
        Initialize the weather screen
        
        Args:
            colors: Color scheme dictionary
        """
        super().__init__("weather", colors)
    
    def setup_ui(self):
        """Set up the UI components"""
        # Create content widget with ID
        content_widget = QWidget()
        content_widget.setObjectName("weather")
        content_layout = QVBoxLayout(content_widget)
        
        # Create centered layout
        centered_layout = QVBoxLayout()
        centered_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Placeholder label
        self.placeholder = QLabel("Weather Screen - Coming Soon")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add to layout
        centered_layout.addWidget(self.placeholder)
        
        # Add centered layout to content layout
        content_layout.addLayout(centered_layout)
        
        # Add content widget to main layout
        self.layout.addWidget(content_widget, 1)  # Stretch to fill remaining space
    
    def apply_styling(self):
        """Apply styling to the screen"""
        super().apply_styling()
        
        # Add additional styling for the weather screen
        additional_style = f"""
            #weather QLabel {{
                color: {self.colors['text_primary']};
                font-size: 24px;
            }}
        """
        self.setStyleSheet(self.styleSheet() + additional_style)
    
    def on_activate(self):
        """Called when this screen becomes active"""
        logger.debug("Weather screen activated")
    
    def on_deactivate(self):
        """Called when this screen becomes inactive"""
        logger.debug("Weather screen deactivated")
    
    def cleanup(self):
        """Clean up resources used by this screen"""
        pass 
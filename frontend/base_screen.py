#!/usr/bin/env python3
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal

class BaseScreen(QWidget):
    """
    Base class for all screen widgets in the application.
    All screens should inherit from this class to ensure a consistent interface.
    """
    # Signal emitted when screen wants to switch to another screen
    request_screen_change = pyqtSignal(str)
    
    def __init__(self, colors):
        super().__init__()
        self.colors = colors
        
    def activate(self):
        """Called when the screen becomes active"""
        pass
        
    def deactivate(self):
        """Called when the screen is about to be hidden"""
        pass
        
    def update_colors(self, colors):
        """Update the color scheme"""
        self.colors = colors
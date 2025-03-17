#!/usr/bin/env python3
"""
ScreenWidget - Base widget class for all screens in the container window.
Provides common functionality for all screen types in the QStackedWidget architecture.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

from frontend.style import DARK_COLORS, LIGHT_COLORS
from frontend.themeable import Themeable

class ScreenWidget(QWidget, Themeable):
    """Base class for all screen widgets that will be used in the container."""
    
    # Signals
    theme_changed = pyqtSignal(bool)  # True for dark mode, False for light mode
    screen_switch_requested = pyqtSignal(str)  # Request to switch to another screen
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize state
        self.is_dark_mode = True
        self.colors = DARK_COLORS
        self.is_kiosk_mode = False
        
        # Setup UI
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        # Create top layout for navigation buttons
        self.top_layout = QHBoxLayout()
        self.main_layout.addLayout(self.top_layout)
        
        # Create navigation buttons layout (hidden by default)
        self.nav_layout = QHBoxLayout()
        self.nav_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.top_layout.addLayout(self.nav_layout)
        self.top_layout.addStretch(1)  # Push nav buttons to the left
        
        # Create content area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.content_widget, 1)  # Add with stretch
        
        # Call method for specific content
        self.setup_ui_content()
        
        # Hide navigation buttons by default
        self.show_navigation_buttons(False)
        
        # Apply initial theming
        self.update_theme(self.is_dark_mode, self.colors)
        
        # Ensure the widget has a solid background
        self.setAutoFillBackground(True)
    
    def setup_ui_content(self):
        """To be implemented by subclasses to add specific content."""
        pass
    
    def add_navigation_button(self, screen_name, display_name):
        """Add a navigation button for switching to another screen."""
        button = QPushButton(display_name)
        button.setFixedHeight(32)
        button.clicked.connect(lambda: self.screen_switch_requested.emit(screen_name))
        self.nav_layout.addWidget(button)
        return button
    
    def show_navigation_buttons(self, visible):
        """Show or hide navigation buttons."""
        for i in range(self.nav_layout.count()):
            item = self.nav_layout.itemAt(i)
            if item and item.widget():
                item.widget().setVisible(visible)
    
    def update_theme(self, is_dark_mode, colors):
        """Update theme for dark/light mode"""
        self.is_dark_mode = is_dark_mode
        self.colors = colors
        
        # Set background color for solid background during transitions
        background_color = colors["background"]
        self.setStyleSheet(f"background-color: {background_color};")
        
        # Ensure solid background
        self.setAutoFillBackground(True)
        
        # Emit signal for other components that might need to update
        self.theme_changed.emit(is_dark_mode)
        
        # Apply theme to all Themeable children
        for child in self.findChildren(Themeable):
            child.update_theme(is_dark_mode, colors)
    
    def toggle_theme(self):
        """Toggle between light and dark themes."""
        self.is_dark_mode = not self.is_dark_mode
        self.colors = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS
        self.update_theme(self.is_dark_mode, self.colors)
        self.theme_changed.emit(self.is_dark_mode)
    
    def set_kiosk_mode(self, enabled):
        """Set kiosk mode state."""
        self.is_kiosk_mode = enabled
        self.show_navigation_buttons(enabled)
    
    def prepare(self):
        """Prepare this screen before it becomes visible."""
        # Override in subclasses if needed
        pass
    
    def cleanup(self):
        """Clean up resources when this screen is no longer needed."""
        # Override in subclasses if needed
        pass 
#!/usr/bin/env python3
"""
ClockScreen - Screen widget for displaying a clock.
Converted from ClockWindow to use the ScreenWidget architecture.
"""

from datetime import datetime
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont

from frontend.screen_widget import ScreenWidget
from frontend.config import logger
from frontend.ui import TopButtons

class ClockScreen(ScreenWidget):
    """
    Clock screen that displays the current time and date in a large, readable format.
    This is the converted version of ClockWindow, adapted to work with the ScreenWidget approach.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ClockScreen")
        
        # Create timer to update clock every second
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # Update every 1000ms (1 second)
        
        # Initial time update
        self.update_time()
        
        # Add navigation buttons for switching to other screens
        self.add_navigation_button("chat", "Chat")
    
    def setup_ui_content(self):
        """Setup the clock UI content"""
        # Create top buttons for consistent UI with chat screen
        self.top_buttons = TopButtons()
        self.content_layout.addWidget(self.top_buttons)
        
        # Connect top buttons signals
        self.top_buttons.theme_toggled.connect(self.toggle_theme)
        self.top_buttons.window_switch_requested.connect(self.screen_switch_requested)
        
        # Set initial state for kiosk mode
        self.top_buttons.set_kiosk_mode(self.is_kiosk_mode)
        self.top_buttons.update_icons(self.is_dark_mode)
        
        # Create container widget with centered alignment
        clock_container = QWidget()
        clock_layout = QVBoxLayout(clock_container)
        clock_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create time label
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_font = QFont()
        time_font.setPointSize(72)
        time_font.setBold(True)
        self.time_label.setFont(time_font)
        
        # Create date label
        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_font = QFont()
        date_font.setPointSize(24)
        self.date_label.setFont(date_font)
        
        # Add labels to layout
        clock_layout.addWidget(self.time_label)
        clock_layout.addWidget(self.date_label)
        
        # Add clock container to content layout
        self.content_layout.addWidget(clock_container, 1)  # Add with stretch
    
    @pyqtSlot()
    def update_time(self):
        """Update the time and date labels with current time"""
        now = datetime.now()
        
        # Update time label (HH:MM:SS)
        time_text = now.strftime("%H:%M:%S")
        self.time_label.setText(time_text)
        
        # Update date label (Weekday, Month Day, Year)
        date_text = now.strftime("%A, %B %d, %Y")
        self.date_label.setText(date_text)
    
    def update_theme(self, is_dark_mode, colors):
        """Update theme colors in this widget."""
        # Call parent implementation
        super().update_theme(is_dark_mode, colors)
        
        # Update top buttons if they exist
        if hasattr(self, 'top_buttons'):
            self.top_buttons.update_icons(is_dark_mode)
    
    def set_kiosk_mode(self, enabled):
        """Set kiosk mode state."""
        # Call parent implementation
        super().set_kiosk_mode(enabled)
        
        # Update top buttons if they exist
        if hasattr(self, 'top_buttons'):
            self.top_buttons.set_kiosk_mode(enabled)
    
    def prepare(self):
        """Prepare this screen before it becomes visible."""
        # Start the timer when screen becomes visible
        if not self.timer.isActive():
            logger.info("ClockScreen: Starting timer")
            self.timer.start(1000)
    
    def cleanup(self):
        """Clean up resources when this screen is no longer needed."""
        # Stop the timer to prevent updates when screen is not visible
        if self.timer.isActive():
            logger.info("ClockScreen: Stopping timer")
            self.timer.stop() 
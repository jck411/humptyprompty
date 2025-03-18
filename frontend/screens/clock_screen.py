#!/usr/bin/env python3
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer, QTime, QDate
from PyQt6.QtGui import QFont

from frontend.base_screen import BaseScreen
from frontend.config import logger

class ClockScreen(BaseScreen):
    """
    Screen that displays the current time and date.
    """
    def __init__(self, colors):
        """
        Initialize the clock screen
        
        Args:
            colors: Color scheme dictionary
        """
        super().__init__("clock", colors)
        
        # Initialize timer for clock updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        
    def setup_ui(self):
        """Set up the UI components"""
        # Create content widget with ID
        content_widget = QWidget()
        content_widget.setObjectName("clock")
        content_layout = QVBoxLayout(content_widget)
        
        # Create centered layout
        centered_layout = QVBoxLayout()
        centered_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Time label
        self.time_label = QLabel("00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Arial", 72, QFont.Weight.Bold)
        self.time_label.setFont(font)
        
        # Date label
        self.date_label = QLabel("Monday, January 1, 2023")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_font = QFont("Arial", 18)
        self.date_label.setFont(date_font)
        
        # Add to layout
        centered_layout.addWidget(self.time_label)
        centered_layout.addWidget(self.date_label)
        
        # Add centered layout to content layout
        content_layout.addLayout(centered_layout)
        
        # Add content widget to main layout
        self.layout.addWidget(content_widget, 1)  # Stretch to fill remaining space
        
        # Update time initially
        self.update_time()
    
    def apply_styling(self):
        """Apply styling to the screen"""
        super().apply_styling()
        
        # Add additional styling for the clock screen
        additional_style = f"""
            #clock QLabel {{
                color: {self.colors['text_primary']};
            }}
        """
        self.setStyleSheet(self.styleSheet() + additional_style)
    
    def update_time(self):
        """Update the displayed time and date"""
        current_time = QTime.currentTime()
        current_date = QDate.currentDate()
        
        # Update time label
        time_text = current_time.toString("hh:mm:ss")
        self.time_label.setText(time_text)
        
        # Update date label
        date_text = current_date.toString("dddd, MMMM d, yyyy")
        self.date_label.setText(date_text)
    
    def on_activate(self):
        """Called when this screen becomes active"""
        logger.debug("Clock screen activated")
        # Start the timer to update every second
        self.timer.start(1000)
        # Update time immediately
        self.update_time()
    
    def on_deactivate(self):
        """Called when this screen becomes inactive"""
        logger.debug("Clock screen deactivated")
        # Stop the timer when not visible
        self.timer.stop()
    
    def cleanup(self):
        """Clean up resources used by this screen"""
        self.timer.stop()
        logger.debug("Clock screen cleaned up") 
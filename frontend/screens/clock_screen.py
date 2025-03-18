#!/usr/bin/env python3
from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import QTimer, Qt, QDateTime
from PyQt6.QtGui import QFont

from frontend.base_screen import BaseScreen

class ClockScreen(BaseScreen):
    """
    Screen that displays the current time and date.
    """
    def __init__(self, colors):
        super().__init__(colors)
        
        # Setup UI components
        self.setup_ui()
        
        # Create timer for updating the clock
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        
    def setup_ui(self):
        """Setup the UI components"""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create time label
        self.time_label = QLabel("00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_font = QFont()
        time_font.setPointSize(72)
        time_font.setBold(True)
        self.time_label.setFont(time_font)
        
        # Create date label
        self.date_label = QLabel("Monday, January 1, 2025")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_font = QFont()
        date_font.setPointSize(24)
        self.date_label.setFont(date_font)
        
        # Add labels to layout
        main_layout.addWidget(self.time_label)
        main_layout.addWidget(self.date_label)
        
        # Apply initial styling
        self.update_colors(self.colors)
        
    def update_time(self):
        """Update the time and date labels"""
        current_datetime = QDateTime.currentDateTime()
        
        # Update time label
        time_text = current_datetime.toString("hh:mm:ss")
        self.time_label.setText(time_text)
        
        # Update date label
        date_text = current_datetime.toString("dddd, MMMM d, yyyy")
        self.date_label.setText(date_text)
        
    def activate(self):
        """Called when the screen becomes active"""
        # Start the timer to update every second
        self.timer.start(1000)
        # Update time immediately
        self.update_time()
        
    def deactivate(self):
        """Called when the screen is about to be hidden"""
        # Stop the timer when the screen is not visible
        self.timer.stop()
        
    def update_colors(self, colors):
        """Update the color scheme"""
        super().update_colors(colors)
        
        # Update label colors
        self.time_label.setStyleSheet(f"color: {colors['text_primary']};")
        self.date_label.setStyleSheet(f"color: {colors['text_primary']};")

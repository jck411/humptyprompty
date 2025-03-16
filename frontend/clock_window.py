#!/usr/bin/env python3
import time
from datetime import datetime
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont

from frontend.base_window import BaseWindow
from frontend.config import logger
from frontend.ui import TopButtons

class ClockWindow(BaseWindow):
    """
    Clock window that displays the current time and date in a large, readable format.
    """
    def __init__(self):
        super().__init__(title="Smart Display - Clock")
        
        # Create timer to update clock every second
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # Update every 1000ms (1 second)
        
        # Initial time update
        self.update_time()
        
        # Hide navigation buttons by default (only shown in kiosk mode)
        self.show_navigation_buttons(False)
    
    def setup_ui_content(self):
        """Setup the clock UI content"""
        # Create top buttons for consistent UI with chat window
        self.top_buttons = TopButtons()
        self.content_layout.addWidget(self.top_buttons)
        
        # Connect top buttons signals
        self.top_buttons.theme_toggled.connect(self.toggle_theme)
        self.top_buttons.window_switch_requested.connect(self.window_switch_requested)
        
        # Set initial state for kiosk mode
        self.top_buttons.set_kiosk_mode(self.is_kiosk_mode)
        
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
    
    def handle_theme_changed(self, is_dark_mode):
        """Handle theme changes"""
        if hasattr(self, 'top_buttons'):
            self.top_buttons.update_theme_icon(is_dark_mode)
    
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
    
    def showEvent(self, event):
        """Handle show event - start timer when window becomes visible"""
        self.timer.start()
        
        # If in kiosk mode, make sure we're properly in fullscreen
        if self.is_kiosk_mode:
            logger.info("ClockWindow: Ensuring fullscreen in kiosk mode")
            self.showFullScreen()
            
        super().showEvent(event)
    
    def hideEvent(self, event):
        """Handle hide event - stop timer when window becomes hidden"""
        self.timer.stop()
        super().hideEvent(event) 
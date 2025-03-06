#!/usr/bin/env python3
import sys
import asyncio
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer

from frontend.config import logger
from frontend.style import DARK_COLORS, LIGHT_COLORS, generate_main_stylesheet
from frontend.chat_controller import ChatController
from frontend.ui import ChatArea, InputArea, TopButtons

class ChatWindow(QMainWindow):
    """
    Main chat window that integrates all UI components and the controller.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Chat Interface")
        self.setMinimumSize(800, 600)
        
        # Initialize state
        self.is_dark_mode = True
        self.colors = DARK_COLORS
        
        # Create controller
        self.controller = ChatController()
        
        # Setup UI components
        self.setup_ui()
        
        # Connect signals
        self.connect_signals()
        
        # Initialize controller
        QTimer.singleShot(0, self.controller.initialize)
        
        # Initial theme setup
        self.top_buttons.update_theme_icon(self.is_dark_mode)
    
    def setup_ui(self):
        """Setup the UI components"""
        # Create central widget and main layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create UI components
        self.top_buttons = TopButtons()
        self.chat_area = ChatArea(self.colors)
        self.input_area = InputArea(self.colors)
        
        # Add components to main layout
        main_layout.addWidget(self.top_buttons)
        main_layout.addWidget(self.chat_area, stretch=1)
        main_layout.addWidget(self.input_area)
        
        # Apply initial styling
        self.apply_styling()
    
    def connect_signals(self):
        """Connect signals between UI components and controller"""
        # Connect top buttons signals
        self.top_buttons.stt_toggled.connect(self.controller.toggle_stt)
        self.top_buttons.tts_toggled.connect(lambda: asyncio.create_task(self.controller.toggle_tts_async()))
        self.top_buttons.clear_clicked.connect(self.clear_chat)
        self.top_buttons.theme_toggled.connect(self.toggle_theme)
        
        # Connect input area signals
        self.input_area.send_clicked.connect(self.send_message)
        self.input_area.stop_clicked.connect(lambda: asyncio.create_task(self.controller.stop_tts_and_generation_async()))
        
        # Connect controller signals
        self.controller.message_received.connect(self.chat_area.update_assistant_message)
        self.controller.assistant_message_finalized.connect(self.chat_area.finalize_assistant_message)
        self.controller.connection_status_changed.connect(self.handle_connection_status)
        self.controller.stt_state_changed.connect(self.top_buttons.update_stt_state)
        self.controller.tts_state_changed.connect(self.top_buttons.update_tts_state)
        self.controller.final_stt_text_received.connect(self.handle_stt_text)
    
    def apply_styling(self):
        """Apply styling to all components"""
        self.setStyleSheet(generate_main_stylesheet(self.colors))
        self.chat_area.update_colors(self.colors)
        self.input_area.update_colors(self.colors)
    
    def toggle_theme(self):
        """Toggle between light and dark theme"""
        self.is_dark_mode = not self.is_dark_mode
        self.colors = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS
        self.top_buttons.update_theme_icon(self.is_dark_mode)
        self.apply_styling()
    
    def send_message(self):
        """Send a message from the input area"""
        text = self.input_area.get_text().strip()
        if text:
            if self.controller.send_message(text):
                self.chat_area.add_message(text, True)
                self.input_area.clear_text()
    
    def clear_chat(self):
        """Clear the chat history"""
        self.chat_area.clear()
        self.controller.clear_chat_history()
    
    def handle_connection_status(self, connected):
        """Handle connection status changes"""
        self.setWindowTitle(f"Modern Chat Interface - {'Connected' if connected else 'Disconnected'}")
    
    def handle_stt_text(self, text):
        """Handle final STT text"""
        self.input_area.text_input.setPlainText(text)
        self.input_area.adjust_text_input_height()
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Closing application...")
        self.controller.cleanup()
        super().closeEvent(event)

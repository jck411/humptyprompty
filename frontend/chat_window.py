#!/usr/bin/env python3
import sys
import asyncio
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

from frontend.config import logger
from frontend.style import DARK_COLORS, LIGHT_COLORS, generate_main_stylesheet
from frontend.chat_controller import ChatController
from frontend.ui import ChatArea, InputArea, TopButtons
from frontend.base_window import BaseWindow

class ChatWindow(BaseWindow):
    """
    Main chat window that integrates all UI components and the controller.
    """
    def __init__(self):
        # Create controller before initializing UI
        self.controller = ChatController()
        
        # Initialize the base window
        super().__init__(title="Smart Display - Chat")
        
        # Initialize controller
        QTimer.singleShot(0, self.controller.initialize)
        
        # Connect controller signals
        self.connect_signals()
    
    def setup_ui_content(self):
        """Setup the chat UI content - implemented as required by BaseWindow"""
        # Create UI components
        self.top_buttons = TopButtons()
        self.chat_area = ChatArea(self.colors)
        self.input_area = InputArea(self.colors)
        
        # Add components to content layout
        self.content_layout.addWidget(self.top_buttons)
        self.content_layout.addWidget(self.chat_area, stretch=1)
        self.content_layout.addWidget(self.input_area)
        
        # Set initial states
        self.top_buttons.update_icons(self.is_dark_mode)
        self.top_buttons.set_kiosk_mode(self.is_kiosk_mode)
    
    def connect_signals(self):
        """Connect signals between UI components and controller"""
        # Connect top buttons signals
        self.top_buttons.stt_toggled.connect(self.controller.toggle_stt)
        self.top_buttons.tts_toggled.connect(lambda: asyncio.create_task(self.controller.toggle_tts_async()))
        self.top_buttons.auto_send_toggled.connect(self.controller.toggle_auto_send)
        self.top_buttons.clear_clicked.connect(self.clear_chat)
        self.top_buttons.theme_toggled.connect(self.toggle_theme)
        self.top_buttons.stop_clicked.connect(lambda: asyncio.create_task(self.controller.stop_tts_and_generation_async()))
        self.top_buttons.window_switch_requested.connect(self.window_switch_requested)
        
        # Connect input area signals
        self.input_area.send_clicked.connect(self.send_message)
        
        # Connect controller signals
        self.controller.message_received.connect(self.chat_area.update_assistant_message)
        self.controller.assistant_message_finalized.connect(self.chat_area.finalize_assistant_message)
        self.controller.connection_status_changed.connect(self.handle_connection_status)
        
        # Connect theme changed signal from base window
        self.theme_changed.connect(self.handle_theme_changed)
    
    def handle_theme_changed(self, is_dark_mode):
        """Handle theme changes from the base window"""
        self.top_buttons.update_icons(is_dark_mode)
        self.chat_area.update_colors(self.colors)
        self.input_area.update_colors(self.colors)
    
    def clear_chat(self):
        """Clear the chat area"""
        self.chat_area.clear()
        self.controller.clear_chat_history()
    
    def send_message(self):
        """Send a message to the controller"""
        message = self.input_area.get_text()
        if message.strip():
            # Add user message to chat area
            self.chat_area.add_message(message, is_user=True)
            # Process message with controller
            self.controller.send_message(message)
            # Clear input area
            self.input_area.clear_text()
    
    def handle_connection_status(self, is_connected):
        """Handle connection status changes"""
        self.input_area.setEnabled(is_connected)
    
    def closeEvent(self, event):
        """Handle window close event - cleanup resources"""
        self.controller.cleanup()
        super().closeEvent(event)

    def toggle_kiosk_mode(self):
        """Override toggle_kiosk_mode to handle input area visibility"""
        # Call the parent class method first to handle the base functionality
        super().toggle_kiosk_mode()
        
        # Update input area visibility based on kiosk mode
        if hasattr(self, 'input_area'):
            self.input_area.setVisible(not self.is_kiosk_mode)
            logger.info(f"ChatWindow: Input area visibility set to {not self.is_kiosk_mode}")
            
    def showEvent(self, event):
        """Handle show event - ensure fullscreen if in kiosk mode"""
        # If in kiosk mode, make sure we're properly in fullscreen
        if self.is_kiosk_mode:
            logger.info("ChatWindow: Ensuring fullscreen in kiosk mode")
            self.showFullScreen()
            
            # Also ensure input area is hidden in kiosk mode
            if hasattr(self, 'input_area'):
                self.input_area.setVisible(not self.is_kiosk_mode)
                
        super().showEvent(event)

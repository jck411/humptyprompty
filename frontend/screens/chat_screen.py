#!/usr/bin/env python3
import asyncio
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QTimer, QSize

from frontend.base_screen import BaseScreen
from frontend.chat_controller import ChatController
from frontend.ui import ChatArea, InputArea, TopButtons
from frontend.config import logger
from frontend.icons import ICON_RETURN

class ChatScreen(BaseScreen):
    """
    Screen that displays the chat interface with AI assistant.
    """
    def __init__(self, colors):
        """
        Initialize the chat screen
        
        Args:
            colors: Color scheme dictionary
        """
        # Create controller before calling parent init
        self.controller = ChatController()
        
        # Call parent init which will call setup_ui
        super().__init__("chat", colors)
        
        # Initialize controller when screen is ready
        QTimer.singleShot(0, self.controller.initialize)
    
    def setup_ui(self):
        """Set up the UI components"""
        # Create content widget with ID
        content_widget = QWidget()
        content_widget.setObjectName("chat")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create UI components
        self.top_buttons = TopButtons()
        self.chat_area = ChatArea(self.colors)
        self.input_area = InputArea(self.colors)
        
        # Create a return button to go back to auto-rotating screens
        return_layout = QHBoxLayout()
        self.return_button = QPushButton("Return to Information Screens")
        self.return_button.setObjectName("return_button")
        self.return_button.setIcon(ICON_RETURN())
        self.return_button.setIconSize(QSize(24, 24))
        self.return_button.clicked.connect(lambda: self.navigate_to("clock"))
        return_layout.addWidget(self.return_button)
        return_layout.addStretch()
        
        # Add components to content layout
        content_layout.addWidget(self.top_buttons)
        content_layout.addWidget(self.chat_area, stretch=1)
        content_layout.addLayout(return_layout)
        content_layout.addWidget(self.input_area)
        
        # Add content widget to main layout
        self.layout.addWidget(content_widget, 1)  # Stretch to fill remaining space
        
        # Connect signals
        self.connect_signals()
    
    def connect_signals(self):
        """Connect signals between UI components and controller"""
        # Connect top buttons signals
        self.top_buttons.stt_toggled.connect(self.controller.toggle_stt)
        self.top_buttons.tts_toggled.connect(lambda: asyncio.create_task(self.controller.toggle_tts_async()))
        self.top_buttons.auto_send_toggled.connect(self.controller.toggle_auto_send)
        self.top_buttons.clear_clicked.connect(self.clear_chat)
        self.top_buttons.stop_clicked.connect(lambda: asyncio.create_task(self.controller.stop_tts_and_generation_async()))
        self.top_buttons.sound_toggled.connect(lambda: asyncio.create_task(self.controller.toggle_tts_async()))
        
        # Connect input area signals
        self.input_area.send_clicked.connect(self.send_message)
        
        # Connect controller signals
        self.controller.message_received.connect(self.chat_area.update_assistant_message)
        self.controller.assistant_message_finalized.connect(self.chat_area.finalize_assistant_message)
        self.controller.connection_status_changed.connect(self.handle_connection_status)
        self.controller.stt_state_changed.connect(self.top_buttons.update_stt_state)
        self.controller.tts_state_changed.connect(self.top_buttons.update_tts_state)
        self.controller.tts_state_changed.connect(self.handle_tts_state_change)
        self.controller.auto_send_state_changed.connect(self.top_buttons.update_auto_send_state)
        self.controller.final_stt_text_received.connect(self.handle_stt_text)
        self.controller.user_message_added.connect(lambda text: self.chat_area.add_message(text, True))
    
    def apply_styling(self):
        """Apply styling to the screen"""
        super().apply_styling()
        
        # Add specific styling for the return button
        additional_style = f"""
            #chat QPushButton#return_button {{
                background-color: {self.colors['button_primary']};
                color: white;
                padding: 12px 20px;
                font-weight: bold;
                font-size: 18px;
                min-height: 50px;
                margin: 10px 0;
                border-radius: 10px;
            }}
            
            #chat QPushButton#return_button:hover {{
                background-color: {self.colors['button_hover']};
            }}
        """
        self.setStyleSheet(self.styleSheet() + additional_style)
        
    def update_colors(self, is_dark_mode=None, colors=None):
        """
        Update the color scheme
        
        Args:
            is_dark_mode: Whether dark mode is enabled (optional)
            colors: New color scheme dictionary (optional)
        """
        # Handle different parameter formats
        if colors is None and isinstance(is_dark_mode, dict):
            # Called with just colors as first parameter
            colors = is_dark_mode
            is_dark_mode = None
            
        if colors:
            super().update_colors(colors)
            self.chat_area.update_colors(colors)
            self.input_area.update_colors(colors)
    
    def send_message(self):
        """Send a message from the input area"""
        text = self.input_area.get_text().strip()
        if text:
            if self.controller.send_message(text):
                self.input_area.clear_text()
    
    def clear_chat(self):
        """Clear the chat history"""
        self.chat_area.clear()
        self.controller.clear_chat_history()
    
    def handle_connection_status(self, connected):
        """Handle connection status changes"""
        # Nothing to do here as the window title is handled by main window
        pass
    
    def handle_stt_text(self, text):
        """Handle final STT text"""
        self.input_area.text_input.setPlainText(text)
        self.input_area.adjust_text_input_height()
    
    def handle_tts_state_change(self, is_enabled):
        """Handle TTS state change"""
        # No kiosk mode handling here as it's handled by main window
        pass
    
    def on_activate(self):
        """Called when this screen becomes active"""
        logger.debug("Chat screen activated")
        # Nothing special to do here
    
    def on_deactivate(self):
        """Called when this screen becomes inactive"""
        logger.debug("Chat screen deactivated")
        # Nothing special to do here
    
    def cleanup(self):
        """Clean up resources used by this screen"""
        logger.debug("Chat screen cleaning up")
        self.controller.cleanup() 
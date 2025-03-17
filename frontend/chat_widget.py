#!/usr/bin/env python3
"""
ChatScreen - Screen widget for displaying and interacting with chat.
Converted from ChatWindow to use the ScreenWidget architecture.
"""

import asyncio
from PyQt6.QtCore import QTimer

from frontend.screen_widget import ScreenWidget
from frontend.chat_controller import ChatController
from frontend.ui import ChatArea, InputArea, TopButtons
from frontend.config import logger

class ChatScreen(ScreenWidget):
    """
    Main chat screen that integrates all UI components and the controller.
    This is the converted version of ChatWindow, adapted to work with the ScreenWidget approach.
    """
    
    def __init__(self, parent=None):
        # Create controller before initializing UI
        self.controller = ChatController()
        
        # Initialize the base screen widget
        super().__init__(parent)
        self.setObjectName("ChatScreen")
        
        # Add navigation buttons for switching to other screens
        self.add_navigation_button("clock", "Clock")
        
        # Initialize controller
        QTimer.singleShot(0, self.controller.initialize)
        
        # Connect controller signals
        self.connect_signals()
    
    def setup_ui_content(self):
        """Setup the chat UI content"""
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
        self.top_buttons.window_switch_requested.connect(self.screen_switch_requested)
        
        # Connect controller signals to top_buttons
        self.controller.stt_state_changed.connect(self.top_buttons.update_stt_state)
        self.controller.tts_state_changed.connect(self.top_buttons.update_tts_state)
        self.controller.auto_send_state_changed.connect(self.top_buttons.update_auto_send_state)
        
        # Connect input area signals
        self.input_area.send_clicked.connect(self.send_message)
        
        # Connect controller signals
        self.controller.message_received.connect(self.chat_area.update_assistant_message)
        self.controller.assistant_message_finalized.connect(self.chat_area.finalize_assistant_message)
        self.controller.connection_status_changed.connect(self.handle_connection_status)
        
        # Connect STT text signals
        self.controller.interim_stt_text_received.connect(self.handle_interim_stt_text)
        self.controller.final_stt_text_received.connect(self.handle_final_stt_text)
    
    def handle_interim_stt_text(self, text):
        """Handle interim STT text from speech recognition"""
        if text.strip():
            # Show interim text in input area, but don't send it
            self.input_area.set_text(text)
    
    def handle_final_stt_text(self, text):
        """Handle final STT text from speech recognition"""
        if text.strip():
            # Display the text in the input area
            self.input_area.set_text(text)
            
            # Always add the transcribed text as a user message in the chat area
            self.chat_area.add_message(text, is_user=True)
            
            # Auto-send vs manual handling:
            # 1. If auto-send is enabled, the controller will send the message automatically
            #    via its handle_final_stt_text method - no need to do anything here
            # 2. If auto-send is disabled, we still want to add it to the chat history
            #    but not send it to the backend
            if not self.controller.auto_send_enabled:
                self.controller.add_message(text, True)
            
            # Clear the input area regardless of auto-send status
            self.input_area.clear_text()
    
    def handle_connection_status(self, is_connected):
        """Handle connection status changes"""
        self.input_area.setEnabled(is_connected)
    
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
    
    def update_theme(self, is_dark_mode, colors):
        """Update theme colors in this widget."""
        # Call parent implementation
        super().update_theme(is_dark_mode, colors)
        
        # Update UI components with new theme
        if hasattr(self, 'top_buttons'):
            self.top_buttons.update_icons(is_dark_mode)
        
        if hasattr(self, 'chat_area'):
            self.chat_area.update_colors(colors)
            
        if hasattr(self, 'input_area'):
            self.input_area.update_colors(colors)
    
    def set_kiosk_mode(self, enabled):
        """Set kiosk mode state."""
        # Call parent implementation
        super().set_kiosk_mode(enabled)
        
        # Update UI components with kiosk mode state
        if hasattr(self, 'top_buttons'):
            self.top_buttons.set_kiosk_mode(enabled)
            
        # In kiosk mode, hide the input area
        if hasattr(self, 'input_area'):
            self.input_area.setVisible(not enabled)
            logger.info(f"ChatScreen: Input area visibility set to {not enabled}")
    
    def prepare(self):
        """Prepare this screen before it becomes visible."""
        logger.info("ChatScreen: Preparing screen")
        # Re-enable controller components if needed
        if hasattr(self, 'controller'):
            # Additional preparation logic can be added here if needed
            pass
    
    async def cleanup(self):
        """Clean up resources when this screen is no longer needed."""
        logger.info("ChatScreen: Cleaning up resources")
        # Clean up the controller if it exists
        if hasattr(self, 'controller'):
            try:
                if hasattr(self.controller, 'cleanup'):
                    if asyncio.iscoroutinefunction(self.controller.cleanup):
                        await self.controller.cleanup()
                    else:
                        self.controller.cleanup()
            except Exception as e:
                logger.error(f"Error during controller cleanup: {e}") 
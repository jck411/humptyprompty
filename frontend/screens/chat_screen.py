#!/usr/bin/env python3
import sys
import asyncio
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtCore import QTimer

from frontend.base_screen import BaseScreen
from frontend.ui import ChatArea, InputArea, TopButtons
from frontend.chat_controller import ChatController
from frontend.config import logger

class ChatScreen(BaseScreen):
    """
    Screen that integrates the existing chat functionality.
    """
    def __init__(self, colors):
        super().__init__(colors)
        
        # Initialize state
        self.is_dark_mode = True
        
        # Create controller
        self.controller = ChatController()
        
        # Setup UI components
        self.setup_ui()
        
        # Connect signals
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the UI components"""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)
        
        # Store reference to main layout
        self.main_layout = main_layout
        
        # Create UI components - pass False to hide theme button
        self.top_buttons = TopButtons(show_theme_button=False)
        self.chat_area = ChatArea(self.colors)
        self.input_area = InputArea(self.colors)
        
        # Add components to main layout
        main_layout.addWidget(self.top_buttons)
        main_layout.addWidget(self.chat_area, stretch=1)
        main_layout.addWidget(self.input_area)
    
    def connect_signals(self):
        """Connect signals between UI components and controller"""
        # Connect top buttons signals
        self.top_buttons.stt_toggled.connect(self.controller.toggle_stt)
        self.top_buttons.tts_toggled.connect(self.handle_tts_toggle)
        self.top_buttons.auto_send_toggled.connect(self.controller.toggle_auto_send)
        self.top_buttons.clear_clicked.connect(self.clear_chat)
        # Stop button - direct call to synchronous stop method instead of async
        self.top_buttons.stop_clicked.connect(self.stop_all)
        
        # Connect input area signals
        self.input_area.send_clicked.connect(self.send_message)
        
        # Connect controller signals
        self.controller.message_received.connect(self.chat_area.update_assistant_message)
        self.controller.assistant_message_finalized.connect(self.chat_area.finalize_assistant_message)
        self.controller.connection_status_changed.connect(self.handle_connection_status)
        self.controller.stt_state_changed.connect(self.handle_stt_state_change)
        self.controller.tts_state_changed.connect(self.top_buttons.update_tts_state)
        self.controller.auto_send_state_changed.connect(self.top_buttons.update_auto_send_state)
        self.controller.final_stt_text_received.connect(self.handle_stt_text)
        self.controller.interim_stt_text_received.connect(self.handle_interim_stt_text)
        self.controller.user_message_added.connect(lambda text: self.chat_area.add_message(text, True))
    
    def handle_tts_toggle(self):
        """Handle TTS toggle button click - ensure it runs immediately"""
        # Create the task directly and immediately
        asyncio.create_task(self.controller.toggle_tts_async())
        
    def stop_all(self):
        """Immediately stop text generation and audio playback"""
        logger.info("Stop button pressed - stopping all generation and audio")
        
        # Call stop_tts_and_generation_async directly which will:
        # 1. Stop audio playback
        # 2. Stop text generation
        # 3. Reset context for the next message
        asyncio.create_task(self.controller.stop_tts_and_generation_async())
        
        # Finalize any assistant message that's in progress
        if self.chat_area.assistant_bubble_in_progress:
            logger.info("Finalizing in-progress assistant message")
            self.controller.assistant_message_finalized.emit()
        
    def activate(self):
        """Initialize controller when the screen becomes active"""
        # Use a QTimer to ensure there's a running event loop
        QTimer.singleShot(0, self.controller.initialize)

    def deactivate(self):
        """Clean up when the screen is hidden"""
        # Ensure top_buttons is back in our layout when screen is hidden
        if self.top_buttons.parent() != self:
            # If top_buttons has been moved elsewhere, bring it back
            self.top_buttons.setParent(None)
            self.main_layout.insertWidget(0, self.top_buttons)
        
    def update_colors(self, colors):
        """Update the color scheme"""
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
        pass  # Not updating window title anymore, handled by main window
    
    def handle_stt_state_change(self, is_enabled, is_listening, is_text_chat):
        """Handle STT state changes"""
        # Update the top buttons
        self.top_buttons.update_stt_state(is_enabled, is_listening, is_text_chat)
        
        # Control input area visibility based on mode
        # Show input elements only in text chat mode
        self.input_area.set_input_elements_visible(is_text_chat)
        
    def handle_interim_stt_text(self, text):
        """Handle interim STT text"""
        if self.controller.stt_enabled and text.strip():
            # Update or create an STT transcript bubble
            self.chat_area.update_transcription(text)

    def handle_stt_text(self, text):
        """Handle final STT text"""
        if self.controller.stt_enabled and text.strip():
            # Remove any transcription bubble first
            self.chat_area.remove_transcription_bubble()
            
            # For final text, just display it as a user message when auto-send is enabled
            if not self.controller.auto_send_enabled:
                self.input_area.text_input.setPlainText(text)
                self.input_area.adjust_text_input_height()
                self.send_message()
        
    def cleanup(self):
        """Clean up resources before closing"""
        self.controller.cleanup()
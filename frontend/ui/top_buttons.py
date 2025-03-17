#!/usr/bin/env python3
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPainter, QColor
from frontend.config import logger
from frontend.icons import get_icon  # Import the centralized icon getter
from frontend.themeable import Themeable
import PyQt6.QtWidgets
import PyQt6.QtGui
import os
import tempfile
import time

class TopButtons(QWidget, Themeable):
    """
    UI component for the top buttons area of the chat window.
    """
    # Signals
    stt_toggled = pyqtSignal()
    tts_toggled = pyqtSignal()
    clear_clicked = pyqtSignal()
    theme_toggled = pyqtSignal()
    auto_send_toggled = pyqtSignal()
    stop_clicked = pyqtSignal()
    window_switch_requested = pyqtSignal(str)  # Emitted when user wants to switch to another window
    
    def __init__(self):
        super().__init__()
        
        # Setup main layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 5, 0, 0)
        self.main_layout.setSpacing(5)
        
        # Create components
        self._create_control_buttons()
        self._create_action_buttons()
        self._create_navigation_buttons()
        
        # Default to not kiosk mode and dark theme
        self.is_kiosk_mode = False
        self.is_dark_mode = True  # Default to dark mode
        
        # Update navigation icons for the initial theme
        self.update_icons(self.is_dark_mode)
        
        # Update layout
        self._update_layout()
    
    def _create_control_buttons(self):
        """Create control buttons (STT, AUTO, TTS)"""
        # Create container
        self.left_buttons_container = QWidget()
        self.left_layout = QHBoxLayout(self.left_buttons_container)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(5)
        
        # Create STT toggle button
        self.stt_button = QPushButton("STT Off")
        self.stt_button.setFixedSize(120, 40)
        self.stt_button.setObjectName("sttButton")
        self.stt_button.setProperty("isEnabled", "false")
        self.stt_button.setProperty("isListening", "false")
        self.stt_button.clicked.connect(self.on_stt_toggled)
        
        # Create auto-send toggle button
        self.auto_send_button = QPushButton("AUTO Off")
        self.auto_send_button.setFixedSize(120, 40)
        self.auto_send_button.setObjectName("autoSendButton")
        self.auto_send_button.setProperty("isAutoSend", "false")
        self.auto_send_button.clicked.connect(self.on_auto_send_toggled)
        
        # Create TTS toggle button
        self.tts_button = QPushButton("TTS Off")
        self.tts_button.setFixedSize(120, 40)
        self.tts_button.setObjectName("ttsButton")
        self.tts_button.setProperty("isTtsEnabled", "false")
        self.tts_button.clicked.connect(self.on_tts_toggled)
        
        # Add buttons to left layout
        self.left_layout.addWidget(self.stt_button)
        self.left_layout.addWidget(self.auto_send_button)
        self.left_layout.addWidget(self.tts_button)
        self.left_layout.addStretch()
    
    def _create_navigation_buttons(self):
        """Create navigation buttons for window switching"""
        # Create clock navigation button
        self.clock_button = QPushButton()
        self.clock_button.setFixedSize(45, 45)
        self.clock_button.setIcon(get_icon('clock'))
        self.clock_button.setIconSize(QSize(30, 30))
        self.clock_button.clicked.connect(lambda: self.window_switch_requested.emit("clock"))
        self.clock_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        
        # Create chat navigation button
        self.chat_button = QPushButton()
        self.chat_button.setFixedSize(45, 45)
        self.chat_button.setIcon(get_icon('chat'))
        self.chat_button.setIconSize(QSize(30, 30))
        self.chat_button.clicked.connect(lambda: self.window_switch_requested.emit("chat"))
        self.chat_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        
        # Set initial icon colors based on current theme
        # This will be called later when the theme is known
    
    def _create_action_buttons(self):
        """Create action buttons (MIC, STOP, CLEAR, THEME)"""
        # Create mic indicator button (only visible when listening)
        self.mic_button = QPushButton()
        self.mic_button.setFixedSize(45, 45)
        self.mic_button.setIcon(get_icon('mic'))
        self.mic_button.setIconSize(QSize(30, 30))
        self.mic_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        self.mic_button.setVisible(False)  # Initially hidden
        
        # Create stop button
        self.stop_button = QPushButton()
        self.stop_button.setFixedSize(45, 45)
        self.stop_button.setIcon(get_icon('stop_all'))
        self.stop_button.setIconSize(QSize(30, 30))
        self.stop_button.clicked.connect(self.on_stop_clicked)
        self.stop_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        
        # Create clear chat button
        self.clear_button = QPushButton()
        self.clear_button.setFixedSize(45, 45)
        self.clear_button.setIcon(get_icon('clear_all'))
        self.clear_button.setIconSize(QSize(30, 30))
        self.clear_button.clicked.connect(self.on_clear_clicked)
        self.clear_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        
        # Create TTS toggle icon button for kiosk mode
        self.tts_icon_button = QPushButton()
        self.tts_icon_button.setFixedSize(45, 45)
        self.tts_icon_button.setIcon(get_icon('sound_on'))
        self.tts_icon_button.setIconSize(QSize(30, 30))
        self.tts_icon_button.clicked.connect(self.on_tts_toggled)
        self.tts_icon_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        self.tts_icon_button.setToolTip("Toggle text-to-speech")
        
        # Create theme toggle button
        self.theme_button = QPushButton()
        self.theme_button.setFixedSize(45, 45)
        self.theme_button.setIcon(get_icon('theme'))
        self.theme_button.setIconSize(QSize(35, 35))
        self.theme_button.clicked.connect(self.on_theme_toggled)
        self.theme_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
    
    def _update_layout(self):
        """Update the layout based on kiosk mode state"""
        # Clear current layout
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        
        # Add components to layout based on mode
        if not self.is_kiosk_mode:
            # Regular mode - include all controls
            self.main_layout.addWidget(self.left_buttons_container, stretch=1)
            self.main_layout.addWidget(self.mic_button)
            self.main_layout.addWidget(self.stop_button)
            self.main_layout.addWidget(self.clear_button)
            # Always show navigation buttons in the regular mode too
            self.main_layout.addWidget(self.chat_button)
            self.main_layout.addWidget(self.clock_button)
            self.main_layout.addWidget(self.theme_button)
            logger.info("TopButtons: Layout updated for regular mode")
        else:
            # Kiosk mode - only include essential controls
            # Add a stretchable empty widget to push buttons to the right
            spacer = QWidget()
            spacer.setSizePolicy(
                PyQt6.QtWidgets.QSizePolicy.Policy.Expanding, 
                PyQt6.QtWidgets.QSizePolicy.Policy.Preferred
            )
            self.main_layout.addWidget(spacer, stretch=1)
            
            # Add the mic button to show when listening in kiosk mode
            self.main_layout.addWidget(self.mic_button)
            
            # Add the stop button for stopping STT and responses
            self.main_layout.addWidget(self.stop_button)
            
            # Add the TTS icon button in kiosk mode
            self.main_layout.addWidget(self.tts_icon_button)
            
            # Always show both navigation buttons regardless of current window
            self.main_layout.addWidget(self.chat_button)
            self.main_layout.addWidget(self.clock_button)
            self.main_layout.addWidget(self.clear_button)
            self.main_layout.addWidget(self.theme_button)
            logger.info("TopButtons: Layout updated for kiosk mode with all navigation buttons")
            
            # Explicitly update the navigation icons when layout changes
            self.update_icons(self.is_dark_mode)
        
        # Update the layout
        self.updateGeometry()
        if self.parent():
            self.parent().updateGeometry()
    
    def on_stt_toggled(self):
        """Handle STT button click"""
        self.stt_toggled.emit()
    
    def on_tts_toggled(self):
        """Handle TTS button click"""
        self.tts_toggled.emit()
    
    def on_auto_send_toggled(self):
        """Handle auto-send button click"""
        # Only emit the signal if the button is enabled (which means STT is on)
        if self.auto_send_button.isEnabled():
            self.auto_send_toggled.emit()
    
    def on_clear_clicked(self):
        """Handle clear button click"""
        self.clear_clicked.emit()
    
    def on_theme_toggled(self):
        """Handle theme button click"""
        self.theme_toggled.emit()
        
    def on_stop_clicked(self):
        """Handle stop button click"""
        self.stop_clicked.emit()
    
    def update_stt_state(self, is_enabled, is_listening=False):
        """
        Update the STT button state
        
        Args:
            is_enabled: Whether STT is enabled (on/off)
            is_listening: Whether STT is actively listening (red state)
        """
        # Update button text
        self.stt_button.setText(f"STT {'On' if is_enabled else 'Off'}")
        
        # Set properties for CSS selector - using strings for stylesheet compatibility
        self.stt_button.setProperty("isEnabled", "true" if is_enabled else "false")
        self.stt_button.setProperty("isListening", "true" if is_listening else "false")
        
        # Show/hide mic icon based on listening state
        self.mic_button.setVisible(is_listening)
        
        # Disable Auto Send button when STT is off
        self.auto_send_button.setEnabled(is_enabled)
        if not is_enabled:
            self.auto_send_button.setText("AUTO Off")
            self.auto_send_button.setProperty("isAutoSend", "false")
        
        # Force style update
        style = self.stt_button.style()
        if style:
            style.unpolish(self.stt_button)
            style.polish(self.stt_button)
        
        # Force UI update
        self.stt_button.update()
        logger.info(f"Updated STT button state: enabled={is_enabled}, listening={is_listening}")
    
    def update_tts_state(self, is_enabled):
        """Update TTS button state based on controller state"""
        # Update button text
        self.tts_button.setText(f"TTS {'On' if is_enabled else 'Off'}")
        
        # Set property for CSS selector - using strings for stylesheet compatibility
        self.tts_button.setProperty("isTtsEnabled", "true" if is_enabled else "false")
        
        # Force style update
        style = self.tts_button.style()
        if style:
            style.unpolish(self.tts_button)
            style.polish(self.tts_button)
        
        # Force UI update
        self.tts_button.update()
        
        # Also update the icon for the kiosk mode TTS button
        if is_enabled:
            self.tts_icon_button.setIcon(get_icon('sound_on'))
            self.tts_icon_button.setToolTip("Text-to-Speech: On (click to disable)")
        else:
            self.tts_icon_button.setIcon(get_icon('sound_off'))
            self.tts_icon_button.setToolTip("Text-to-Speech: Off (click to enable)")
        
        logger.info(f"Updated TTS button state: enabled={is_enabled}")
    
    def update_auto_send_state(self, is_enabled):
        """Update the auto-send button state"""
        # Update button text
        self.auto_send_button.setText(f"AUTO {'On' if is_enabled else 'Off'}")
        
        # Set property for CSS selector - using strings for stylesheet compatibility
        self.auto_send_button.setProperty("isAutoSend", "true" if is_enabled else "false")
        
        # Force style update
        style = self.auto_send_button.style()
        if style:
            style.unpolish(self.auto_send_button)
            style.polish(self.auto_send_button)
        
        # Force UI update
        self.auto_send_button.update()
        logger.info(f"Updated AUTO button state: enabled={is_enabled}")
    
    def update_icons(self, is_dark_mode):
        """Update the icon colors based on theme"""
        self.is_dark_mode = is_dark_mode
        
        # The SVG icons are designed to work with both themes using their own internal colors
        # No color changes are needed for the icons as they automatically adapt to the theme
        logger.info(f"Theme updated to {'dark' if is_dark_mode else 'light'} mode - icons remain unchanged")
        
        # If we need to refresh the icons for any reason, we can do it here
        # but we don't need to change their colors
        icon_widgets = [
            self.clock_button, 
            self.chat_button, 
            self.mic_button, 
            self.stop_button, 
            self.clear_button, 
            self.theme_button,
            self.tts_icon_button
        ]
        
        # Ensure icons are properly displayed
        for widget in icon_widgets:
            if hasattr(widget, 'iconSize') and callable(widget.iconSize):
                current_size = widget.iconSize()
                widget.setIconSize(QSize(current_size.width(), current_size.height()))
    
    def set_kiosk_mode(self, is_kiosk_mode):
        """Update UI for kiosk/fullscreen mode"""
        if self.is_kiosk_mode == is_kiosk_mode:
            return  # No change
            
        logger.info(f"TopButtons: Updating for kiosk mode: {is_kiosk_mode}")
        self.is_kiosk_mode = is_kiosk_mode
        
        # Update layout
        self._update_layout()
        
        # If switching to kiosk mode, make sure the TTS icon reflects the current state
        if is_kiosk_mode:
            # Get current TTS state from the button
            is_tts_enabled = self.tts_button.property("isTtsEnabled")
            # Update the icon to match
            if is_tts_enabled:
                self.tts_icon_button.setIcon(get_icon('sound_on'))
                self.tts_icon_button.setToolTip("Text-to-Speech: On (click to disable)")
            else:
                self.tts_icon_button.setIcon(get_icon('sound_off'))
                self.tts_icon_button.setToolTip("Text-to-Speech: Off (click to enable)")
    
    def showEvent(self, event):
        """Handle show event to ensure proper icon colors"""
        super().showEvent(event)
        # Always update icons when the widget becomes visible
        self.update_icons(self.is_dark_mode)
        logger.info("TopButtons: Updated icons on show event") 
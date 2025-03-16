#!/usr/bin/env python3
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPainter, QColor
from frontend.config import logger
import PyQt6.QtWidgets
import PyQt6.QtGui
import os
import tempfile
import time

class TopButtons(QWidget):
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
        self.update_navigation_icons(self.is_dark_mode)
        
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
        self.stt_button.setProperty("isEnabled", False)
        self.stt_button.setProperty("isListening", False)
        self.stt_button.clicked.connect(self.on_stt_toggled)
        
        # Create auto-send toggle button
        self.auto_send_button = QPushButton("AUTO Off")
        self.auto_send_button.setFixedSize(120, 40)
        self.auto_send_button.setObjectName("autoSendButton")
        self.auto_send_button.setProperty("isAutoSend", False)
        self.auto_send_button.clicked.connect(self.on_auto_send_toggled)
        
        # Create TTS toggle button
        self.tts_button = QPushButton("TTS Off")
        self.tts_button.setFixedSize(120, 40)
        self.tts_button.setObjectName("ttsButton")
        self.tts_button.setProperty("isTtsEnabled", False)
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
        self.clock_button.setIcon(QIcon("frontend/icons/clock.svg"))
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
        self.chat_button.setIcon(QIcon("frontend/icons/chat.svg"))
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
        self.mic_button.setIcon(QIcon("frontend/icons/mic.svg"))
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
        self.stop_button.setIcon(QIcon("frontend/icons/stop_all.svg"))
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
        self.clear_button.setIcon(QIcon("frontend/icons/clear_all.svg"))
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
        
        # Create theme toggle button
        self.theme_button = QPushButton()
        self.theme_button.setFixedSize(45, 45)
        self.theme_button.setIcon(QIcon("frontend/icons/dark_mode.svg"))
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
            
            # Get current window type
            current_window_type = self.parent().parent().parent().__class__.__name__.lower().replace('window', '')
            
            # Add navigation buttons (don't show the button for the current window)
            if current_window_type != "chat":
                self.main_layout.addWidget(self.chat_button)
            if current_window_type != "clock":
                self.main_layout.addWidget(self.clock_button)
            
            self.main_layout.addWidget(self.clear_button)
            self.main_layout.addWidget(self.theme_button)
            logger.info(f"TopButtons: Layout updated for kiosk mode in {current_window_type} window")
            
            # Explicitly update the navigation icons when layout changes
            self.update_navigation_icons(self.is_dark_mode)
        
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
        self.stt_button.setText(f"STT {'On' if is_enabled else 'Off'}")
        self.stt_button.setProperty("isEnabled", is_enabled)
        self.stt_button.setProperty("isListening", is_listening)
        
        # Show/hide mic icon based on listening state
        self.mic_button.setVisible(is_listening)
        
        # Disable Auto Send button when STT is off
        self.auto_send_button.setEnabled(is_enabled)
        if not is_enabled:
            self.auto_send_button.setText("AUTO Off")
            self.auto_send_button.setProperty("isAutoSend", False)
        
        # Force style update
        style = self.stt_button.style()
        if style:
            style.unpolish(self.stt_button)
            style.polish(self.stt_button)
        self.stt_button.update()
    
    def update_tts_state(self, is_enabled):
        """Update the TTS button state"""
        self.tts_button.setText(f"TTS {'On' if is_enabled else 'Off'}")
        self.tts_button.setProperty("isTtsEnabled", is_enabled)
        
        # Force style update
        style = self.tts_button.style()
        if style:
            style.unpolish(self.tts_button)
            style.polish(self.tts_button)
        self.tts_button.update()
    
    def update_auto_send_state(self, is_enabled):
        """Update the auto-send button state"""
        self.auto_send_button.setText(f"AUTO {'On' if is_enabled else 'Off'}")
        self.auto_send_button.setProperty("isAutoSend", is_enabled)
        
        # Force style update
        style = self.auto_send_button.style()
        if style:
            style.unpolish(self.auto_send_button)
            style.polish(self.auto_send_button)
        self.auto_send_button.update()
    
    def update_theme_icon(self, is_dark_mode):
        """Update the theme button icon based on current theme"""
        icon_path = "frontend/icons/light_mode.svg" if is_dark_mode else "frontend/icons/dark_mode.svg"
        self.theme_button.setIcon(QIcon(icon_path))
        
        # Also update navigation icons to match the theme
        self.update_navigation_icons(is_dark_mode)
    
    def update_navigation_icons(self, is_dark_mode):
        """Update navigation icons to match the current theme"""
        # Store the current theme state
        self.is_dark_mode = is_dark_mode
        
        # Set fill color to match other icons
        fill_color = "#565f89" if is_dark_mode else "#333333"
        
        # Create custom SVGs with the right fill color
        chat_svg = f'<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="{fill_color}"><path d="M240-400h320v-80H240v80Zm0-120h480v-80H240v80Zm0-120h480v-80H240v80ZM80-80v-720q0-33 23.5-56.5T160-880h640q33 0 56.5 23.5T880-800v480q0 33-23.5 56.5T800-240H240L80-80Zm126-240h594v-480H160v525l46-45Zm-46 0v-480 480Z"/></svg>'
        
        clock_svg = f'<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="{fill_color}"><path d="M480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Zm-40 120v-240h80v240h-80Z"/></svg>'
        
        # Ensure temp directory exists
        temp_dir = os.path.join(tempfile.gettempdir(), "humptyprompty_icons")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create temp SVG files with unique timestamps to avoid caching issues
        timestamp = int(os.path.getmtime(__file__)) if os.path.exists(__file__) else int(time.time())
        
        chat_path = os.path.join(temp_dir, f"chat_{fill_color.replace('#', '')}_{timestamp}.svg")
        clock_path = os.path.join(temp_dir, f"clock_{fill_color.replace('#', '')}_{timestamp}.svg")
        
        # Only write the files if they don't exist
        if not os.path.exists(chat_path):
            with open(chat_path, "w") as f:
                f.write(chat_svg)
                
        if not os.path.exists(clock_path):
            with open(clock_path, "w") as f:
                f.write(clock_svg)
        
        # Update icons with QIcon.fromTheme to disable caching
        self.chat_button.setIcon(QIcon())  # Clear the icon first
        self.chat_button.setIcon(QIcon(chat_path))
        self.chat_button.setIconSize(QSize(30, 30))  # Reset icon size to force redraw
        
        self.clock_button.setIcon(QIcon())  # Clear the icon first
        self.clock_button.setIcon(QIcon(clock_path))
        self.clock_button.setIconSize(QSize(30, 30))  # Reset icon size to force redraw
        
        logger.info(f"Updated navigation icons for {'dark' if is_dark_mode else 'light'} theme")
    
    def set_kiosk_mode(self, is_kiosk_mode):
        """
        Show or hide control buttons based on kiosk mode
        
        Args:
            is_kiosk_mode: Whether kiosk mode is active
        """
        if self.is_kiosk_mode == is_kiosk_mode:
            return  # No change
        
        logger.info(f"TopButtons: Setting kiosk mode to {is_kiosk_mode}")
        self.is_kiosk_mode = is_kiosk_mode
        self._update_layout() 

    def showEvent(self, event):
        """Handle show event to ensure proper icon colors"""
        super().showEvent(event)
        # Always update icons when the widget becomes visible
        self.update_navigation_icons(self.is_dark_mode)
        logger.info("TopButtons: Updated icons on show event") 
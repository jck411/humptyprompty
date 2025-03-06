#!/usr/bin/env python3
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QIcon

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
    
    def __init__(self):
        super().__init__()
        
        # Setup main layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 5, 0, 0)
        self.main_layout.setSpacing(5)
        
        # Create left buttons container
        left_buttons = QWidget()
        left_layout = QHBoxLayout(left_buttons)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        
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
        self.tts_button.clicked.connect(self.on_tts_toggled)
        
        # Create clear chat button
        self.clear_button = QPushButton("CLEAR")
        self.clear_button.setFixedSize(120, 40)
        self.clear_button.clicked.connect(self.on_clear_clicked)
        
        # Add buttons to left layout
        left_layout.addWidget(self.stt_button)
        left_layout.addWidget(self.auto_send_button)
        left_layout.addWidget(self.tts_button)
        left_layout.addWidget(self.clear_button)
        left_layout.addStretch()
        
        # Add left buttons to main layout
        self.main_layout.addWidget(left_buttons, stretch=1)
        
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
        
        # Add theme button to main layout
        self.main_layout.addWidget(self.theme_button)
    
    def on_stt_toggled(self):
        """Handle STT button click"""
        self.stt_toggled.emit()
    
    def on_tts_toggled(self):
        """Handle TTS button click"""
        self.tts_toggled.emit()
    
    def on_auto_send_toggled(self):
        """Handle auto-send button click"""
        self.auto_send_toggled.emit()
    
    def on_clear_clicked(self):
        """Handle clear button click"""
        self.clear_clicked.emit()
    
    def on_theme_toggled(self):
        """Handle theme button click"""
        self.theme_toggled.emit()
    
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
        
        # Force style update
        style = self.stt_button.style()
        if style:
            style.unpolish(self.stt_button)
            style.polish(self.stt_button)
        self.stt_button.update()
    
    def update_tts_state(self, is_enabled):
        """Update the TTS button state"""
        self.tts_button.setText(f"TTS {'On' if is_enabled else 'Off'}")
    
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
#!/usr/bin/env python3
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QToolBar, QLabel
from PyQt6.QtCore import pyqtSignal, QSize, Qt, QTimer
from PyQt6.QtGui import QIcon, QFont

class TopButtons(QWidget):
    """
    UI component for the top buttons area of the chat window.
    """
    # Signals
    stt_toggled = pyqtSignal()
    tts_toggled = pyqtSignal()
    clear_clicked = pyqtSignal()
    theme_toggled = pyqtSignal()
    stop_clicked = pyqtSignal()
    
    def __init__(self, show_theme_button=True):
        super().__init__()
        
        # Common button style
        self.button_style = """
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """
        
        # Setup main layout - use QHBoxLayout with fixed alignment
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 5, 0, 0)
        self.main_layout.setSpacing(5)
        
        # Create screen-specific buttons
        self.stt_button = self.create_button("stt_off.svg", 30, "sttButton")
        self.stt_button.setProperty("isEnabled", False)
        self.stt_button.setProperty("isListening", False)
        self.stt_button.setProperty("isTextChat", False)
        self.stt_button.clicked.connect(self.on_stt_toggled)
        
        # Create countdown label (replaces auto-send button)
        self.countdown_label = QLabel("0")
        self.countdown_label.setFixedSize(45, 45)
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.countdown_label.setFont(font)
        self.countdown_label.setStyleSheet("""
            QLabel {
                color: #565f89;
                background-color: transparent;
                border-radius: 20px;
            }
        """)
        self.countdown_label.setVisible(False)  # Initially hidden
        
        # Timer for countdown
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)  # 1 second
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_value = 0
        
        self.tts_button = self.create_button("sound_off.svg", 30, "ttsButton")
        self.tts_button.setProperty("isTtsEnabled", False)
        self.tts_button.clicked.connect(self.on_tts_toggled)
        
        # Create mic indicator button (only visible when listening)
        self.mic_button = self.create_button("mic.svg", 30)
        self.mic_button.setVisible(False)  # Initially hidden
        
        # Create stop button
        self.stop_button = self.create_button("stop_all.svg", 30)
        self.stop_button.clicked.connect(self.on_stop_clicked)
        
        # Create clear chat button
        self.clear_button = self.create_button("clear_all.svg", 30)
        self.clear_button.clicked.connect(self.on_clear_clicked)
        
        # Create theme toggle button
        self.theme_button = self.create_button("dark_mode.svg", 35)
        self.theme_button.clicked.connect(self.on_theme_toggled)
        
        # Add buttons to main layout (modified order)
        self.main_layout.addWidget(self.stt_button)
        self.main_layout.addWidget(self.tts_button)
        self.main_layout.addWidget(self.stop_button)
        self.main_layout.addWidget(self.clear_button)
        self.main_layout.addWidget(self.countdown_label)
        self.main_layout.addWidget(self.mic_button)
        
        # Only add theme button if shown
        if show_theme_button:
            self.main_layout.addWidget(self.theme_button)
        else:
            self.theme_button.setVisible(False)  # Hide if not shown
            
        # Add stretch to push everything to the left
        self.main_layout.addStretch(1)
    
    def create_button(self, icon_name, icon_size, object_name=None):
        """Helper method to create buttons with consistent styling"""
        button = QPushButton()
        button.setFixedSize(45, 45)
        button.setIcon(QIcon(f"frontend/icons/{icon_name}"))
        button.setIconSize(QSize(icon_size, icon_size))
        if object_name:
            button.setObjectName(object_name)
        button.setStyleSheet(self.button_style)
        return button
    
    def on_stt_toggled(self):
        """Handle STT button click"""
        self.stt_toggled.emit()
    
    def on_tts_toggled(self):
        """Handle TTS button click"""
        self.tts_toggled.emit()
    
    def update_countdown(self):
        """Update the countdown timer display"""
        self.countdown_value -= 1
        self.countdown_label.setText(str(self.countdown_value))
        
        if self.countdown_value <= 0:
            self.countdown_timer.stop()
            self.countdown_label.setVisible(False)
    
    def on_clear_clicked(self):
        """Handle clear button click"""
        self.clear_clicked.emit()
    
    def on_theme_toggled(self):
        """Handle theme button click"""
        self.theme_toggled.emit()
        
    def on_stop_clicked(self):
        """Handle stop button click"""
        self.stop_clicked.emit()
    
    def update_stt_state(self, is_enabled, is_listening=False, is_text_chat=False):
        """
        Update the STT button state
        
        Args:
            is_enabled: Whether STT is enabled (on/off)
            is_listening: Whether STT is actively listening (red state)
            is_text_chat: Whether text chat mode is enabled
        """
        # Set the appropriate icon
        if is_enabled:
            self.stt_button.setIcon(QIcon("frontend/icons/stt_on.svg"))
        elif is_text_chat:
            self.stt_button.setIcon(QIcon("frontend/icons/text_chat.svg"))  # Use text_chat icon for text chat mode
        else:
            self.stt_button.setIcon(QIcon("frontend/icons/stt_off.svg"))  # Default icon (chat)
        
        # Update properties
        self.stt_button.setProperty("isEnabled", is_enabled)
        self.stt_button.setProperty("isListening", is_listening)
        self.stt_button.setProperty("isTextChat", is_text_chat)
        
        # Show/hide mic icon based on listening state
        self.mic_button.setVisible(is_listening)
        
        # Show/hide countdown based on STT state
        if is_enabled and is_listening:
            # Start or restart countdown when STT is enabled and listening
            self.start_countdown()
        else:
            # Hide countdown when STT is disabled
            self.countdown_timer.stop()
            self.countdown_label.setVisible(False)
        
        # Force style update
        style = self.stt_button.style()
        if style:
            style.unpolish(self.stt_button)
            style.polish(self.stt_button)
        self.stt_button.update()
    
    def update_tts_state(self, is_enabled):
        """Update the TTS button state"""
        self.tts_button.setIcon(QIcon(f"frontend/icons/sound_{'on' if is_enabled else 'off'}.svg"))
        self.tts_button.setProperty("isTtsEnabled", is_enabled)
        
        # Force style update
        style = self.tts_button.style()
        if style:
            style.unpolish(self.tts_button)
            style.polish(self.tts_button)
        self.tts_button.update()
    
    def update_auto_send_state(self, is_enabled):
        """Update the auto-send state and start countdown if enabled"""
        if is_enabled:
            self.start_countdown()
        else:
            self.countdown_timer.stop()
            self.countdown_label.setVisible(False)
    
    def start_countdown(self, seconds=15):
        """
        Start or restart the countdown timer
        
        This countdown reflects the Deepgram keepalive timeout (default 15 seconds).
        When the countdown reaches 0, the STT will automatically disable itself.
        """
        self.countdown_timer.stop()
        self.countdown_value = seconds
        self.countdown_label.setText(str(self.countdown_value))
        self.countdown_label.setVisible(True)
        self.countdown_timer.start()
    
    def update_theme_icon(self, is_dark_mode):
        """Update the theme button icon based on current theme"""
        icon_path = "frontend/icons/light_mode.svg" if is_dark_mode else "frontend/icons/dark_mode.svg"
        self.theme_button.setIcon(QIcon(icon_path))

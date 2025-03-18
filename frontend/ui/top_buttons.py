#!/usr/bin/env python3
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QGraphicsOpacityEffect
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
    stop_clicked = pyqtSignal()
    
    def __init__(self, show_theme_button=True):
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
        
        # Create mic indicator button (always takes up space, but icon only visible when listening)
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
        self.mic_button.setProperty("isListening", False)
        # Set icon opacity to 0 instead of hiding the button
        self.set_button_opacity(self.mic_button, 0)
        
        # Create STT toggle button
        self.stt_button = QPushButton()
        self.stt_button.setFixedSize(45, 45)
        self.stt_button.setIcon(QIcon("frontend/icons/stt_off.svg"))
        self.stt_button.setIconSize(QSize(30, 30))
        self.stt_button.setObjectName("sttButton")
        self.stt_button.setProperty("isEnabled", False)
        self.stt_button.setProperty("isListening", False)
        self.stt_button.clicked.connect(self.on_stt_toggled)
        self.stt_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        
        # Create auto-send toggle button
        self.auto_send_button = QPushButton()
        self.auto_send_button.setFixedSize(45, 45)
        self.auto_send_button.setIcon(QIcon("frontend/icons/auto_send_off.svg"))
        self.auto_send_button.setIconSize(QSize(30, 30))
        self.auto_send_button.setObjectName("autoSendButton")
        self.auto_send_button.setProperty("isAutoSend", False)
        self.auto_send_button.clicked.connect(self.on_auto_send_toggled)
        self.auto_send_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        
        # Create TTS toggle button
        self.tts_button = QPushButton()
        self.tts_button.setFixedSize(45, 45)
        self.tts_button.setIcon(QIcon("frontend/icons/sound_off.svg"))
        self.tts_button.setIconSize(QSize(30, 30))
        self.tts_button.setObjectName("ttsButton")
        self.tts_button.setProperty("isTtsEnabled", False)
        self.tts_button.clicked.connect(self.on_tts_toggled)
        self.tts_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        
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
        
        # Create clear button
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
        
        # Add buttons to left layout in specified order: MIC/STT/AUTO/TTS/STOP/CLEAR
        left_layout.addWidget(self.mic_button)
        left_layout.addWidget(self.stt_button)
        left_layout.addWidget(self.auto_send_button)
        left_layout.addWidget(self.tts_button)
        left_layout.addWidget(self.stop_button)
        left_layout.addWidget(self.clear_button)
        left_layout.addStretch()
        
        # Add left buttons to main layout
        self.main_layout.addWidget(left_buttons, stretch=1)
        
        # Create theme toggle button (optional)
        if show_theme_button:
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
        else:
            self.theme_button = None
        
        # Store buttons that should be hidden in kiosk mode
        self.normal_mode_buttons = [self.stt_button, self.auto_send_button, 
                                   self.tts_button, self.stop_button, 
                                   self.clear_button, self.mic_button]
        
        # Default is normal mode
        self.is_kiosk_mode = False
    
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
        self.stt_button.setIcon(QIcon(f"frontend/icons/stt_{'on' if is_enabled else 'off'}.svg"))
        self.stt_button.setProperty("isEnabled", is_enabled)
        self.stt_button.setProperty("isListening", is_listening)
        
        # Show/hide mic icon by changing opacity instead of visibility
        # This preserves the space for the icon, preventing layout shifts
        opacity = 1 if is_listening else 0
        self.set_button_opacity(self.mic_button, opacity)
        self.mic_button.setProperty("isListening", is_listening)
        
        # Disable Auto Send button when STT is off
        self.auto_send_button.setEnabled(is_enabled)
        if not is_enabled:
            self.auto_send_button.setIcon(QIcon("frontend/icons/auto_send_off.svg"))
            self.auto_send_button.setProperty("isAutoSend", False)
        
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
        """Update the auto-send button state"""
        self.auto_send_button.setIcon(QIcon(f"frontend/icons/auto_send_{'on' if is_enabled else 'off'}.svg"))
        self.auto_send_button.setProperty("isAutoSend", is_enabled)
        
        # Force style update
        style = self.auto_send_button.style()
        if style:
            style.unpolish(self.auto_send_button)
            style.polish(self.auto_send_button)
        self.auto_send_button.update()
    
    def update_theme_icon(self, is_dark_mode):
        """Update the theme button icon based on current theme"""
        if self.theme_button:
            icon_path = "frontend/icons/light_mode.svg" if is_dark_mode else "frontend/icons/dark_mode.svg"
            self.theme_button.setIcon(QIcon(icon_path))
    
    def set_kiosk_mode(self, is_kiosk_mode):
        """Toggle between kiosk mode and normal mode
        
        Args:
            is_kiosk_mode: True for kiosk mode (only theme button visible),
                          False for normal mode (all buttons visible)
        """
        self.is_kiosk_mode = is_kiosk_mode
        
        # Show/hide buttons based on mode
        for button in self.normal_mode_buttons:
            button.setVisible(not is_kiosk_mode)
        
        # If returning to normal mode, restore mic opacity based on listening state
        if not is_kiosk_mode:
            is_listening = self.stt_button.property("isListening")
            opacity = 1 if is_listening else 0
            self.set_button_opacity(self.mic_button, opacity)
    
    def set_button_opacity(self, button, opacity):
        """Set the opacity of a button's icon while preserving its space in layout
        
        Args:
            button: The button to modify
            opacity: Opacity value (0-1), where 0 is invisible and 1 is fully visible
        """
        # Don't completely replace the button's stylesheet, instead just set opacity on the icon
        button.setProperty("iconOpacity", opacity)
        
        # Update the icon opacity using QGraphicsOpacityEffect
        effect = QGraphicsOpacityEffect(button)
        effect.setOpacity(opacity)
        button.setGraphicsEffect(effect)
        
        # Make sure the button is always visible in the layout
        button.setVisible(True)
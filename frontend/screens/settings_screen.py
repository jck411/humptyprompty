#!/usr/bin/env python3
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QWidget, QHBoxLayout, 
    QPushButton, QSlider, QCheckBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from frontend.base_screen import BaseScreen

class SettingsScreen(BaseScreen):
    """
    Screen that displays application settings.
    This is a placeholder implementation with common settings.
    """
    # Signal for when settings are changed
    settings_changed = pyqtSignal(dict)
    
    def __init__(self, colors):
        super().__init__(colors)
        
        # Initialize settings
        self.settings = {
            "rotation_interval": 30,  # seconds
            "auto_rotation": True,
            "volume": 75,  # percent
            "wake_word_enabled": True,
            "tts_enabled": True,
            "stt_enabled": True,
        }
        
        # Setup UI components
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI components"""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)
        
        # Create title
        title_label = QLabel("Settings")
        title_font = QFont()
        title_font.setPointSize(36)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create settings sections
        display_section = self.create_display_section()
        audio_section = self.create_audio_section()
        voice_section = self.create_voice_section()
        
        # Add sections to main layout
        main_layout.addWidget(title_label)
        main_layout.addWidget(display_section)
        main_layout.addWidget(audio_section)
        main_layout.addWidget(voice_section)
        main_layout.addStretch()
        
        # Apply initial styling
        self.update_colors(self.colors)
        
    def create_section_title(self, title):
        """Create a section title label"""
        label = QLabel(title)
        section_font = QFont()
        section_font.setPointSize(18)
        section_font.setBold(True)
        label.setFont(section_font)
        return label
        
    def create_display_section(self):
        """Create the display settings section"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Section title
        title = self.create_section_title("Display")
        layout.addWidget(title)
        
        # Auto rotation setting
        auto_rotation_widget = QWidget()
        auto_rotation_layout = QHBoxLayout(auto_rotation_widget)
        auto_rotation_layout.setContentsMargins(20, 0, 0, 0)
        
        auto_rotation_label = QLabel("Auto Rotation:")
        self.auto_rotation_checkbox = QCheckBox()
        self.auto_rotation_checkbox.setChecked(self.settings["auto_rotation"])
        self.auto_rotation_checkbox.stateChanged.connect(self.on_auto_rotation_changed)
        
        auto_rotation_layout.addWidget(auto_rotation_label)
        auto_rotation_layout.addStretch()
        auto_rotation_layout.addWidget(self.auto_rotation_checkbox)
        
        # Rotation interval setting
        rotation_interval_widget = QWidget()
        rotation_interval_layout = QHBoxLayout(rotation_interval_widget)
        rotation_interval_layout.setContentsMargins(20, 0, 0, 0)
        
        rotation_interval_label = QLabel("Rotation Interval:")
        self.rotation_interval_combo = QComboBox()
        self.rotation_interval_combo.addItems(["10 seconds", "30 seconds", "1 minute", "5 minutes"])
        self.rotation_interval_combo.setCurrentIndex(1)  # Default to 30 seconds
        self.rotation_interval_combo.currentIndexChanged.connect(self.on_rotation_interval_changed)
        
        rotation_interval_layout.addWidget(rotation_interval_label)
        rotation_interval_layout.addStretch()
        rotation_interval_layout.addWidget(self.rotation_interval_combo)
        
        # Add settings to section
        layout.addWidget(auto_rotation_widget)
        layout.addWidget(rotation_interval_widget)
        
        return section
        
    def create_audio_section(self):
        """Create the audio settings section"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Section title
        title = self.create_section_title("Audio")
        layout.addWidget(title)
        
        # Volume setting
        volume_widget = QWidget()
        volume_layout = QHBoxLayout(volume_widget)
        volume_layout.setContentsMargins(20, 0, 0, 0)
        
        volume_label = QLabel("Volume:")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(self.settings["volume"])
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        
        # Add settings to section
        layout.addWidget(volume_widget)
        
        return section
        
    def create_voice_section(self):
        """Create the voice settings section"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Section title
        title = self.create_section_title("Voice")
        layout.addWidget(title)
        
        # Wake word setting
        wake_word_widget = QWidget()
        wake_word_layout = QHBoxLayout(wake_word_widget)
        wake_word_layout.setContentsMargins(20, 0, 0, 0)
        
        wake_word_label = QLabel("Wake Word Detection:")
        self.wake_word_checkbox = QCheckBox()
        self.wake_word_checkbox.setChecked(self.settings["wake_word_enabled"])
        self.wake_word_checkbox.stateChanged.connect(self.on_wake_word_changed)
        
        wake_word_layout.addWidget(wake_word_label)
        wake_word_layout.addStretch()
        wake_word_layout.addWidget(self.wake_word_checkbox)
        
        # TTS setting
        tts_widget = QWidget()
        tts_layout = QHBoxLayout(tts_widget)
        tts_layout.setContentsMargins(20, 0, 0, 0)
        
        tts_label = QLabel("Text-to-Speech:")
        self.tts_checkbox = QCheckBox()
        self.tts_checkbox.setChecked(self.settings["tts_enabled"])
        self.tts_checkbox.stateChanged.connect(self.on_tts_changed)
        
        tts_layout.addWidget(tts_label)
        tts_layout.addStretch()
        tts_layout.addWidget(self.tts_checkbox)
        
        # STT setting
        stt_widget = QWidget()
        stt_layout = QHBoxLayout(stt_widget)
        stt_layout.setContentsMargins(20, 0, 0, 0)
        
        stt_label = QLabel("Speech-to-Text:")
        self.stt_checkbox = QCheckBox()
        self.stt_checkbox.setChecked(self.settings["stt_enabled"])
        self.stt_checkbox.stateChanged.connect(self.on_stt_changed)
        
        stt_layout.addWidget(stt_label)
        stt_layout.addStretch()
        stt_layout.addWidget(self.stt_checkbox)
        
        # Add settings to section
        layout.addWidget(wake_word_widget)
        layout.addWidget(tts_widget)
        layout.addWidget(stt_widget)
        
        return section
        
    def on_auto_rotation_changed(self, state):
        """Handle auto rotation checkbox state change"""
        self.settings["auto_rotation"] = state == Qt.CheckState.Checked
        self.settings_changed.emit(self.settings)
        
    def on_rotation_interval_changed(self, index):
        """Handle rotation interval combo box change"""
        intervals = [10, 30, 60, 300]  # seconds
        self.settings["rotation_interval"] = intervals[index]
        self.settings_changed.emit(self.settings)
        
    def on_volume_changed(self, value):
        """Handle volume slider change"""
        self.settings["volume"] = value
        self.settings_changed.emit(self.settings)
        
    def on_wake_word_changed(self, state):
        """Handle wake word checkbox state change"""
        self.settings["wake_word_enabled"] = state == Qt.CheckState.Checked
        self.settings_changed.emit(self.settings)
        
    def on_tts_changed(self, state):
        """Handle TTS checkbox state change"""
        self.settings["tts_enabled"] = state == Qt.CheckState.Checked
        self.settings_changed.emit(self.settings)
        
    def on_stt_changed(self, state):
        """Handle STT checkbox state change"""
        self.settings["stt_enabled"] = state == Qt.CheckState.Checked
        self.settings_changed.emit(self.settings)
        
    def activate(self):
        """Called when the screen becomes active"""
        pass
        
    def deactivate(self):
        """Called when the screen is about to be hidden"""
        pass
        
    def update_colors(self, colors):
        """Update the color scheme"""
        super().update_colors(colors)
        
        # Update all labels with the text color
        text_color = f"color: {colors['text_primary']};"
        for widget in self.findChildren(QLabel):
            widget.setStyleSheet(text_color)

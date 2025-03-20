#!/usr/bin/env python3
from PySide6.QtCore import QObject, Signal, Slot, Property
from frontend.config import logger

class AppManager(QObject):
    """
    Manages application-wide state and settings.
    
    This class serves as a central point for managing application state,
    handling cross-component communication, and storing global settings.
    """
    
    # Signals
    sttStateChanged = Signal(bool)
    ttsStateChanged = Signal(bool)
    themeChanged = Signal(str)
    screenChanged = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Application state
        self._current_screen = "chat"
        self._theme = "dark"
        self._stt_active = False
        self._tts_active = True
        self._auto_rotate = True
        self._rotation_interval = 30000  # 30 seconds
        
        logger.info("AppManager initialized")
    
    @Slot(bool)
    def handle_stt_state_change(self, is_active):
        """Handle STT state changes from any component"""
        if self._stt_active != is_active:
            self._stt_active = is_active
            self.sttStateChanged.emit(is_active)
            logger.info(f"App-wide STT state changed to: {is_active}")
    
    @Slot(bool)
    def handle_tts_state_change(self, is_active):
        """Handle TTS state changes from any component"""
        if self._tts_active != is_active:
            self._tts_active = is_active
            self.ttsStateChanged.emit(is_active)
            logger.info(f"App-wide TTS state changed to: {is_active}")
    
    @Slot(str)
    def set_current_screen(self, screen_name):
        """Set the current active screen"""
        if self._current_screen != screen_name:
            self._current_screen = screen_name
            self.screenChanged.emit(screen_name)
            logger.info(f"Screen changed to: {screen_name}")
    
    @Slot(str)
    def set_theme(self, theme):
        """Set the application theme (light/dark)"""
        if self._theme != theme and theme in ["light", "dark"]:
            self._theme = theme
            self.themeChanged.emit(theme)
            logger.info(f"Theme changed to: {theme}")
    
    @Slot(bool)
    def set_auto_rotate(self, enabled):
        """Enable/disable automatic screen rotation"""
        if self._auto_rotate != enabled:
            self._auto_rotate = enabled
            logger.info(f"Auto-rotate set to: {enabled}")
    
    @Slot(int)
    def set_rotation_interval(self, milliseconds):
        """Set the screen rotation interval in milliseconds"""
        if milliseconds >= 5000:  # Minimum 5 seconds
            self._rotation_interval = milliseconds
            logger.info(f"Rotation interval set to: {milliseconds}ms")
    
    # Properties
    @Property(str)
    def currentScreen(self):
        return self._current_screen
    
    @Property(str)
    def theme(self):
        return self._theme
    
    @Property(bool)
    def sttActive(self):
        return self._stt_active
    
    @Property(bool)
    def ttsActive(self):
        return self._tts_active
    
    @Property(bool)
    def autoRotate(self):
        return self._auto_rotate
    
    @Property(int)
    def rotationInterval(self):
        return self._rotation_interval

#!/usr/bin/env python3
from PyQt6.QtWidgets import QStackedWidget
from PyQt6.QtCore import QTimer, pyqtSignal

class ScreenManager(QStackedWidget):
    """
    Manages screen transitions and automatic rotation.
    """
    theme_changed = pyqtSignal(bool)  # Signal for when theme changes (is_dark_mode)
    screen_changed = pyqtSignal(str)  # Signal for when screen changes (screen_name)
    
    def __init__(self, colors):
        super().__init__()
        self.colors = colors
        self.screens = {}  # Dictionary of screen name -> screen widget
        self.rotation_enabled = False
        self.rotation_timer = QTimer(self)
        self.rotation_timer.timeout.connect(self.rotate_screen)
        self.is_dark_mode = True
        
    def add_screen(self, name, screen):
        """Add a screen to the manager with the given name"""
        self.screens[name] = screen
        self.addWidget(screen)
        
        # Connect the screen's request_screen_change signal
        screen.request_screen_change.connect(self.set_current_screen)
        
    def set_current_screen(self, name):
        """Switch to the screen with the given name"""
        if name in self.screens:
            # Deactivate current screen
            current = self.currentWidget()
            if current:
                current.deactivate()
                
            # Activate new screen
            screen = self.screens[name]
            self.setCurrentWidget(screen)
            screen.activate()
            
            # Emit the signal that the screen has changed
            self.screen_changed.emit(name)
            
    def rotate_screen(self):
        """Rotate to the next screen in the sequence"""
        if len(self.screens) <= 1:
            return
            
        current_index = self.currentIndex()
        next_index = (current_index + 1) % self.count()
        
        # Deactivate current screen
        current = self.currentWidget()
        if current:
            current.deactivate()
            
        # Activate next screen
        self.setCurrentIndex(next_index)
        next_screen = self.currentWidget()
        if next_screen:
            next_screen.activate()
            
            # Find screen name and emit signal
            for name, screen in self.screens.items():
                if screen == next_screen:
                    self.screen_changed.emit(name)
                    break
            
    def start_rotation(self, interval=30000):
        """Start automatic screen rotation with the given interval (in ms)"""
        self.rotation_timer.start(interval)
        self.rotation_enabled = True
        
    def stop_rotation(self):
        """Stop automatic screen rotation"""
        self.rotation_timer.stop()
        self.rotation_enabled = False
        
    def toggle_rotation(self, interval=30000):
        """Toggle automatic screen rotation"""
        if self.rotation_enabled:
            self.stop_rotation()
        else:
            self.start_rotation(interval)
            
    def update_colors(self, colors):
        """Update the color scheme for all screens"""
        self.colors = colors
        for screen in self.screens.values():
            screen.update_colors(colors)
            
    def toggle_theme(self):
        """Toggle between light and dark theme"""
        self.is_dark_mode = not self.is_dark_mode
        self.theme_changed.emit(self.is_dark_mode)
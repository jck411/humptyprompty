#!/usr/bin/env python3
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from frontend.config import logger

class ScreenManager(QObject):
    """
    Manages screens in the application, handling transitions and automatic rotation.
    """
    # Signals
    screen_changed = pyqtSignal(str)  # Screen name
    
    def __init__(self, main_window):
        """
        Initialize the screen manager
        
        Args:
            main_window: The main window instance
        """
        super().__init__()
        self.main_window = main_window
        self.screens = {}  # name -> (index, screen_widget)
        self.current_screen = None
        self.auto_rotate = False
        self.rotation_interval = 30000  # 30 seconds default
        self.rotation_sequence = []
        
        # Setup rotation timer
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_to_next_screen)
        
    def add_screen(self, screen, name):
        """
        Add a screen to the manager
        
        Args:
            screen: The screen widget to add
            name: Unique name for the screen
            
        Returns:
            The name of the added screen
        """
        # Add the screen to the main window
        index = self.main_window.add_screen(screen, name)
        
        # Store the screen in our dictionary
        self.screens[name] = (index, screen)
        
        # Connect navigation signal from screen
        screen.navigation_requested.connect(self.show_screen)
        
        # Connect to main window theme changes
        self.main_window.theme_changed.connect(lambda is_dark, colors: screen.update_colors(colors))
        
        # If this is the first screen, make it current
        if len(self.screens) == 1:
            self.current_screen = name
        
        return name
    
    def show_screen(self, name):
        """
        Show the screen with the given name
        
        Args:
            name: Name of the screen to show
        """
        # Handle special commands
        if name == "toggle_theme":
            # Just use the main window's toggle_theme method without changing screens
            self.main_window.toggle_theme()
            return
            
        if name not in self.screens:
            logger.error(f"Screen '{name}' not found")
            return
        
        # Call deactivate on current screen
        if self.current_screen and self.current_screen in self.screens:
            _, current = self.screens[self.current_screen]
            current.on_deactivate()
        
        # Show the new screen
        index, new_screen = self.screens[name]
        self.main_window.show_screen(index)
        
        # Call activate on new screen
        new_screen.on_activate()
        
        # Update current screen
        self.current_screen = name
        
        # Emit signal
        self.screen_changed.emit(name)
        
        # Reset rotation timer if auto-rotate is enabled
        if self.auto_rotate:
            self.rotation_timer.start(self.rotation_interval)
    
    def set_rotation_sequence(self, screen_names, interval_ms=30000):
        """
        Set the sequence of screens to rotate through
        
        Args:
            screen_names: List of screen names in rotation order
            interval_ms: Time in milliseconds between rotations
        """
        # Validate all screen names
        for name in screen_names:
            if name not in self.screens:
                logger.error(f"Screen '{name}' not found, cannot add to rotation")
                return False
        
        self.rotation_sequence = screen_names
        self.rotation_interval = interval_ms
        
        return True
    
    def start_auto_rotation(self):
        """Start automatic screen rotation"""
        if not self.rotation_sequence:
            logger.warning("Cannot start rotation: No rotation sequence set")
            return False
        
        self.auto_rotate = True
        self.rotation_timer.start(self.rotation_interval)
        logger.info("Auto-rotation started")
        
        return True
    
    def stop_auto_rotation(self):
        """Stop automatic screen rotation"""
        self.auto_rotate = False
        self.rotation_timer.stop()
        logger.info("Auto-rotation stopped")
    
    def rotate_to_next_screen(self):
        """Rotate to the next screen in the sequence"""
        if not self.rotation_sequence:
            return
        
        # Find current position in sequence
        try:
            current_index = self.rotation_sequence.index(self.current_screen)
            next_index = (current_index + 1) % len(self.rotation_sequence)
        except ValueError:
            # Current screen not in rotation sequence, start from beginning
            next_index = 0
        
        next_screen = self.rotation_sequence[next_index]
        self.show_screen(next_screen)
    
    def cleanup(self):
        """Clean up resources used by the screen manager"""
        self.rotation_timer.stop()
        
        # Clean up all screens
        for name, (_, screen) in self.screens.items():
            if hasattr(screen, 'cleanup'):
                screen.cleanup() 
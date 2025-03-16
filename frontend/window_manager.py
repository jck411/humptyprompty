#!/usr/bin/env python3
import asyncio
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot, Qt
from typing import List, Dict, Type, Optional

from frontend.base_window import BaseWindow
from frontend.clock_window import ClockWindow
from frontend.chat_window import ChatWindow
from frontend.config import logger
from frontend.style import DARK_COLORS, LIGHT_COLORS

class WindowManager(QObject):
    """
    WindowManager handles the lifecycle and transitions between different window types.
    It manages window creation, rotation, and ensures consistent state across windows.
    """
    # Signals
    window_changed = pyqtSignal(str)  # Emitted when active window changes, with window type name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Window registry for all available window types
        self.window_types: Dict[str, Type[BaseWindow]] = {
            "clock": ClockWindow,
            "chat": ChatWindow,
            # Future window types will be added here
            # "weather": WeatherWindow,
            # "calendar": CalendarWindow,
            # "photos": PhotoWindow,
        }
        
        # Window display names
        self.window_display_names: Dict[str, str] = {
            "clock": "Clock",
            "chat": "Chat",
            # Future window display names will be added here
            # "weather": "Weather",
            # "calendar": "Calendar",
            # "photos": "Photos",
        }
        
        # Active windows instances (created on demand)
        self.windows: Dict[str, BaseWindow] = {}
        
        # Current active window
        self.current_window_name: Optional[str] = None
        self.current_window: Optional[BaseWindow] = None
        
        # Rotation settings
        self.rotation_enabled = True
        self.rotation_interval = 60000  # 60 seconds by default
        self.rotation_order: List[str] = ["clock", "chat"]  # Add more as they're implemented
        self.rotation_index = 0
        
        # Initialize rotation timer
        self.rotation_timer = QTimer(self)
        self.rotation_timer.timeout.connect(self.rotate_to_next_window)
        
    def initialize(self):
        """Initialize the window manager and show the first window"""
        logger.info("Initializing WindowManager")
        
        # Show the chat window first (regardless of rotation order)
        self.show_window("chat")
        
        # Start the rotation timer if enabled (but only for kiosk mode)
        if self.rotation_enabled:
            self.rotation_timer.start(self.rotation_interval)
    
    def get_window(self, window_name: str) -> BaseWindow:
        """Get or create a window instance by name"""
        if window_name not in self.window_types:
            raise ValueError(f"Unknown window type: {window_name}")
            
        # Create the window if it doesn't exist
        if window_name not in self.windows:
            window_class = self.window_types[window_name]
            window = window_class()
            
            # Connect window signals
            window.theme_changed.connect(self.handle_theme_changed)
            window.window_closed.connect(self.handle_window_closed)
            window.window_switch_requested.connect(self.show_window)
            
            # Add navigation buttons to the window (hidden by default)
            self.add_navigation_buttons(window)
            window.show_navigation_buttons(window.is_kiosk_mode)
            
            self.windows[window_name] = window
            logger.info(f"Created new window: {window_name}")
        
        return self.windows[window_name]
    
    def add_navigation_buttons(self, window: BaseWindow):
        """Add navigation buttons to a window"""
        # Add a button for each available window type
        for name, display_name in self.window_display_names.items():
            # Don't add a button for the current window type
            window_type = self._get_window_type(window.__class__.__name__)
            if name != window_type:
                window.add_navigation_button(name, display_name)
    
    def _get_window_type(self, class_name: str) -> str:
        """Get the window type from the class name"""
        # Convert e.g. 'ClockWindow' to 'clock'
        return class_name.lower().replace('window', '')
    
    def show_window(self, window_name: str):
        """Show a specific window and hide the current one"""
        if window_name == self.current_window_name and self.current_window and self.current_window.isVisible():
            logger.info(f"Window {window_name} is already visible")
            return
            
        # Get the window instance
        try:
            window = self.get_window(window_name)
        except ValueError as e:
            logger.error(str(e))
            return
            
        # Ensure kiosk mode is consistent when switching windows
        if self.current_window and self.current_window.is_kiosk_mode and not window.is_kiosk_mode:
            # If we're coming from a window in kiosk mode, make sure the new window is also in kiosk mode
            logger.info(f"Setting {window_name} to kiosk mode to match current window state")
            window.is_kiosk_mode = True
            
            # Apply kiosk mode UI changes
            window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            
            # Update top buttons if they exist
            if hasattr(window, 'top_buttons'):
                logger.info(f"Updating top buttons for {window_name} to kiosk mode")
                window.top_buttons.set_kiosk_mode(True)
                
            # Hide input area if this is a ChatWindow
            if window_name == "chat" and hasattr(window, 'input_area'):
                logger.info(f"Hiding input area for {window_name} in kiosk mode")
                window.input_area.setVisible(False)
            
        # Hide current window if exists
        if self.current_window:
            self.current_window.hide()
            
        # Show new window
        window.show()
        
        # If window should be in kiosk mode, make sure it's in full screen
        if window.is_kiosk_mode:
            logger.info(f"Ensuring {window_name} is in full screen")
            window.showFullScreen()
        
        # Update current window
        self.current_window_name = window_name
        self.current_window = window
        
        # Update rotation index
        if window_name in self.rotation_order:
            self.rotation_index = self.rotation_order.index(window_name)
            
        # Emit signal
        self.window_changed.emit(window_name)
        logger.info(f"Changed active window to: {window_name}")
    
    @pyqtSlot()
    def rotate_to_next_window(self):
        """Rotate to the next window in the rotation order"""
        # Only rotate if current window is in kiosk mode
        if not self.current_window or not self.current_window.is_kiosk_mode:
            return
            
        if not self.rotation_order:
            return
            
        # Increment rotation index
        self.rotation_index = (self.rotation_index + 1) % len(self.rotation_order)
        next_window = self.rotation_order[self.rotation_index]
        
        # Show the next window
        self.show_window(next_window)
    
    @pyqtSlot(bool)
    def handle_theme_changed(self, is_dark_mode: bool):
        """Propagate theme changes to all windows"""
        for window in self.windows.values():
            if window.is_dark_mode != is_dark_mode:
                window.is_dark_mode = is_dark_mode
                window.colors = DARK_COLORS if is_dark_mode else LIGHT_COLORS
                window.apply_styling()
                # Call handle_theme_changed if it exists
                if hasattr(window, 'handle_theme_changed'):
                    window.handle_theme_changed(is_dark_mode)
    
    @pyqtSlot()
    def handle_window_closed(self):
        """Handle when a window is closed"""
        # If the closed window was the current one, remove the reference
        if self.current_window and not self.current_window.isVisible():
            self.current_window = None
            self.current_window_name = None
            
        # Check if all windows are closed
        all_closed = all(not window.isVisible() for window in self.windows.values())
        if all_closed:
            logger.info("All windows closed, stopping rotation timer")
            self.rotation_timer.stop()
    
    def set_rotation_interval(self, interval_ms: int):
        """Set the rotation interval in milliseconds"""
        if interval_ms < 1000:  # Minimum 1 second
            interval_ms = 1000
            
        self.rotation_interval = interval_ms
        
        # Restart timer if it's running
        if self.rotation_timer.isActive():
            self.rotation_timer.stop()
            self.rotation_timer.start(self.rotation_interval)
    
    def toggle_rotation(self, enabled: bool = None):
        """Toggle rotation on/off"""
        if enabled is None:
            self.rotation_enabled = not self.rotation_enabled
        else:
            self.rotation_enabled = enabled
            
        if self.rotation_enabled:
            self.rotation_timer.start(self.rotation_interval)
        else:
            self.rotation_timer.stop()
    
    def cleanup(self):
        """Clean up resources before shutdown"""
        logger.info("Cleaning up WindowManager")
        self.rotation_timer.stop()
        
        # Close all windows
        for name, window in self.windows.items():
            logger.info(f"Closing window: {name}")
            window.close() 
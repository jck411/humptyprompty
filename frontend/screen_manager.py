#!/usr/bin/env python3
"""
ScreenManager - Manages the lifecycle and transitions of screens in the QStackedWidget.
Handles screen registration, initialization, caching, and rotation.
"""

import time
import asyncio
from typing import Dict, List, Type, Optional, Set
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, Qt, QEasingCurve
from PyQt6.QtWidgets import QStackedWidget

from frontend.config import logger
from frontend.style import DARK_COLORS, LIGHT_COLORS
from frontend.themeable import Themeable
from frontend.transitions import ScreenTransitionManager, TransitionType

class ScreenManager(QObject):
    """
    ScreenManager handles the lifecycle and transitions between different screen types.
    It manages screen creation, rotation, and ensures consistent state across screens.
    """
    # Signals
    screen_changed = pyqtSignal(str)  # Emitted when active screen changes, with screen type name
    pre_screen_change = pyqtSignal(str, str)  # Emitted before screen change, with from and to screen names
    post_screen_change = pyqtSignal(str, str)  # Emitted after screen change, with from and to screen names
    
    def __init__(self, stacked_widget, parent=None):
        super().__init__(parent)
        
        # Store reference to the stacked widget
        self.stacked_widget = stacked_widget
        
        # Create transition manager
        self.transition_manager = ScreenTransitionManager(stacked_widget)
        
        # Default transition type
        self.default_transition_type = TransitionType.FADE
        
        # Screen registry for all available screen types
        self.screen_types = {}
        
        # Screen display names
        self.screen_display_names = {}
        
        # Active screen instances (created on demand)
        self.screens = {}
        
        # Current active screen
        self.current_screen_name = None
        self.current_screen = None
        
        # Rotation settings
        self.rotation_enabled = False
        self.rotation_interval = 60000  # 60 seconds by default
        self.rotation_order = []
        self.rotation_index = 0
        
        # Initialize rotation timer
        self.rotation_timer = QTimer(self)
        self.rotation_timer.timeout.connect(self.rotate_to_next_screen)
        
        # Task tracking for async operations
        self._pending_tasks = set()
        
        # Screen memory management
        self.memory_optimization_enabled = False
        self.inactive_screen_timeout = 300000  # 5 minutes
        self.screen_last_used = {}  # Track when each screen was last used
        self.screen_unload_timer = QTimer(self)
        self.screen_unload_timer.timeout.connect(self.check_for_screens_to_unload)
        self.screen_unload_timer.start(60000)  # Check every minute
    
    def register_screen_type(self, screen_name, screen_class, display_name=None):
        """Register a screen type with the manager"""
        self.screen_types[screen_name] = screen_class
        self.screen_display_names[screen_name] = display_name or screen_name.title()
        logger.info(f"Registered screen type: {screen_name}")
        
        # Add to rotation order if not already there
        if screen_name not in self.rotation_order:
            self.rotation_order.append(screen_name)
    
    def initialize(self, start_screen=None):
        """Initialize the screen manager and show the first screen"""
        logger.info("Initializing ScreenManager")
        
        # Show the specified start screen or the first registered screen
        if start_screen:
            self.show_screen(start_screen)
        elif self.rotation_order:
            self.show_screen(self.rotation_order[0])
        
        # Disable automatic rotation by default
        self.rotation_enabled = False
        logger.info("Screen rotation is disabled by default")
    
    def get_screen(self, screen_name):
        """Get or create a screen instance by name"""
        if screen_name not in self.screen_types:
            raise ValueError(f"Unknown screen type: {screen_name}")
            
        # Create the screen if it doesn't exist
        if screen_name not in self.screens:
            screen_class = self.screen_types[screen_name]
            screen = screen_class()
            
            # Connect screen signals to manager methods
            if hasattr(screen, 'screen_switch_requested'):
                screen.screen_switch_requested.connect(self.show_screen)
                
            if hasattr(screen, 'theme_changed'):
                screen.theme_changed.connect(self.handle_theme_changed)
            
            # Add the screen to the stacked widget
            self.stacked_widget.addWidget(screen)
            self.screens[screen_name] = screen
            logger.info(f"Created new screen: {screen_name}")
            
            # Initialize screen with theme if we have one
            if hasattr(self, 'current_theme_is_dark'):
                if hasattr(screen, 'is_dark_mode') and screen.is_dark_mode != self.current_theme_is_dark:
                    self._apply_theme_to_screen(screen, self.current_theme_is_dark)
        
        # Update last used time
        self.screen_last_used[screen_name] = int(time.time() * 1000)
        
        return self.screens[screen_name]
    
    def show_screen(self, screen_name, transition_type=None):
        """
        Show a specific screen with an optional transition type.
        
        Args:
            screen_name: The name of the screen to show
            transition_type: Optional TransitionType to use; if None, uses default
        """
        # If trying to show the current screen, do nothing
        if screen_name == self.current_screen_name:
            return
        
        # Get the requested screen (creates it if needed)
        screen = self.get_screen(screen_name)
        if not screen:
            logger.error(f"Failed to get screen of type {screen_name}")
            return
        
        # Store the previous screen name for transition
        previous_screen_name = self.current_screen_name
        
        # Emit pre-change signal
        self.pre_screen_change.emit(previous_screen_name or "", screen_name)
        
        # Determine transition type to use
        if transition_type is None:
            transition_type = self.default_transition_type
            
        # Prepare the screen before showing it
        if hasattr(screen, 'prepare'):
            screen.prepare()
        
        # Update current screen information
        self.current_screen_name = screen_name
        self.current_screen = screen
        
        # Track when this screen was last used (for memory management)
        self.screen_last_used[screen_name] = int(time.time() * 1000)
        
        # Use transition manager to handle the transition
        self.transition_manager.transition(
            screen, 
            transition_type,
            on_complete=lambda: self._handle_transition_complete(previous_screen_name, screen_name)
        )
    
    def _handle_transition_complete(self, from_screen_name, to_screen_name):
        """Handle completion of a screen transition."""
        # Emit the signal that the screen has changed
        self.screen_changed.emit(to_screen_name)
        
        # Emit post-change signal
        self.post_screen_change.emit(from_screen_name or "", to_screen_name)
        
        # If rotation is enabled, reset the timer
        if self.rotation_enabled:
            self.rotation_timer.start(self.rotation_interval)
        
        # Update internal rotation index if this screen is in the rotation order
        if to_screen_name in self.rotation_order:
            self.rotation_index = self.rotation_order.index(to_screen_name)
    
    def set_default_transition(self, transition_type: TransitionType):
        """Set the default transition type for all screen changes."""
        self.default_transition_type = transition_type
        logger.info(f"Default transition set to: {transition_type.name}")
    
    def set_transition_duration(self, duration_ms: int):
        """Set the duration for all transitions in milliseconds."""
        self.transition_manager.set_duration(duration_ms)
        logger.info(f"Transition duration set to: {duration_ms}ms")
    
    def set_transition_easing(self, easing_curve: QEasingCurve.Type):
        """Set the easing curve for all transitions."""
        self.transition_manager.set_easing_curve(easing_curve)
        logger.info(f"Transition easing curve set to: {easing_curve.name}")
    
    def rotate_to_next_screen(self):
        """Rotate to the next screen in the rotation order"""
        if not self.rotation_enabled:
            return
            
        if not self.rotation_order:
            return
            
        # Increment rotation index
        self.rotation_index = (self.rotation_index + 1) % len(self.rotation_order)
        next_screen = self.rotation_order[self.rotation_index]
        
        # Show the next screen
        self.show_screen(next_screen)
    
    def set_rotation_interval(self, interval_ms):
        """Set the rotation interval in milliseconds"""
        if interval_ms < 1000:  # Minimum 1 second
            interval_ms = 1000
            
        self.rotation_interval = interval_ms
        
        # Restart timer if it's running
        if self.rotation_timer.isActive():
            self.rotation_timer.stop()
            self.rotation_timer.start(self.rotation_interval)
    
    def toggle_rotation(self, enabled=None):
        """Toggle rotation on/off"""
        if enabled is None:
            self.rotation_enabled = not self.rotation_enabled
        else:
            self.rotation_enabled = enabled
            
        if self.rotation_enabled:
            # Only start the timer if not already active
            if not self.rotation_timer.isActive():
                self.rotation_timer.start(self.rotation_interval)
                logger.info(f"Started rotation timer with interval {self.rotation_interval}ms")
        else:
            # Only stop the timer if it's active
            if self.rotation_timer.isActive():
                self.rotation_timer.stop()
                logger.info("Stopped rotation timer")
    
    def handle_theme_changed(self, is_dark_mode):
        """Propagate theme changes to all screens"""
        # Store the current theme state so we can apply it to screens when they become visible
        self.current_theme_is_dark = is_dark_mode
        
        # Update all screens
        for screen_name, screen in self.screens.items():
            self._apply_theme_to_screen(screen, is_dark_mode)
    
    def _apply_theme_to_screen(self, screen, is_dark_mode):
        """Apply theme changes to a specific screen"""
        if hasattr(screen, 'is_dark_mode') and screen.is_dark_mode != is_dark_mode:
            screen.is_dark_mode = is_dark_mode
            if hasattr(screen, 'colors'):
                screen.colors = DARK_COLORS if is_dark_mode else LIGHT_COLORS
            
            # If the screen is a Themeable, use the update_theme method
            if isinstance(screen, Themeable) and hasattr(screen, 'update_theme'):
                screen.update_theme(is_dark_mode, DARK_COLORS if is_dark_mode else LIGHT_COLORS)
    
    def check_for_screens_to_unload(self):
        """Check for screens that have been inactive for a while and unload them to free memory"""
        if not self.memory_optimization_enabled:
            return
            
        # Get current time in milliseconds
        current_time = int(time.time() * 1000)
        screens_to_unload = []
        
        for screen_name, screen in self.screens.items():
            # Never unload the current screen
            if screen_name == self.current_screen_name:
                continue
                
            # Check if the screen has been inactive for long enough
            last_used = self.screen_last_used.get(screen_name, 0)
            if current_time - last_used > self.inactive_screen_timeout:
                screens_to_unload.append(screen_name)
        
        # Unload the screens
        for screen_name in screens_to_unload:
            self.unload_screen(screen_name)
    
    def unload_screen(self, screen_name):
        """Unload a screen to free memory"""
        if screen_name not in self.screens:
            return
            
        logger.info(f"Unloading inactive screen: {screen_name}")
        
        # Get the screen object
        screen = self.screens[screen_name]
        
        # Call cleanup method if it exists
        if hasattr(screen, 'cleanup'):
            screen.cleanup()
        
        # Remove it from our tracking dictionaries
        self.stacked_widget.removeWidget(screen)
        del self.screens[screen_name]
        if screen_name in self.screen_last_used:
            del self.screen_last_used[screen_name]
            
        # Clean up the screen
        screen.deleteLater()
    
    def set_memory_optimization(self, enabled, timeout_ms=None):
        """Enable or disable memory optimization by unloading inactive screens"""
        self.memory_optimization_enabled = enabled
        
        if timeout_ms is not None:
            self.inactive_screen_timeout = max(timeout_ms, 60000)  # Minimum 1 minute
            
        logger.info(f"Memory optimization {'enabled' if enabled else 'disabled'} " 
                   f"with timeout {self.inactive_screen_timeout}ms")
    
    async def cleanup(self):
        """Clean up resources before shutdown"""
        logger.info("Cleaning up ScreenManager")
        
        # Stop timers
        self.rotation_timer.stop()
        self.screen_unload_timer.stop()
        
        # Clean up all screens
        for name, screen in list(self.screens.items()):
            logger.info(f"Cleaning up screen: {name}")
            
            # Handle async cleanup
            if hasattr(screen, 'cleanup'):
                if asyncio.iscoroutinefunction(screen.cleanup):
                    try:
                        await screen.cleanup()
                    except Exception as e:
                        logger.error(f"Error during screen cleanup: {e}")
                else:
                    try:
                        screen.cleanup()
                    except Exception as e:
                        logger.error(f"Error during screen cleanup: {e}")
            
        logger.info("ScreenManager cleanup complete") 
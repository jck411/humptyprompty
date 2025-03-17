#!/usr/bin/env python3
import asyncio
import time
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot, Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QWidget
from typing import List, Dict, Type, Optional, Set

from frontend.base_window import BaseWindow
from frontend.clock_window import ClockWindow
from frontend.chat_window import ChatWindow
from frontend.config import logger
from frontend.style import DARK_COLORS, LIGHT_COLORS
from frontend.themeable import Themeable

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
        
        # Register window classes in BaseWindow.WINDOW_CLASSES dictionary
        for window_type, window_class in self.window_types.items():
            BaseWindow.register_window_class(window_type, window_class)
        
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
        
        # Task tracking
        self._pending_tasks: Set[asyncio.Task] = set()
        
        # Window memory management
        self.memory_optimization_enabled = False
        self.inactive_window_timeout = 300000  # 5 minutes
        self.window_last_used = {}  # Track when each window was last used
        self.window_unload_timer = QTimer(self)
        self.window_unload_timer.timeout.connect(self.check_for_windows_to_unload)
        self.window_unload_timer.start(60000)  # Check every minute
        
    def initialize(self):
        """Initialize the window manager and show the first window"""
        logger.info("Initializing WindowManager")
        
        # Show the chat window first (regardless of rotation order)
        self.show_window("chat")
        
        # Disable automatic rotation by default
        self.rotation_enabled = False
        logger.info("Window rotation is disabled by default")
        
        # We'll only start the rotation timer when it's explicitly enabled
        # This avoids wasting resources with a timer that fires but does nothing
    
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
            
        # Store reference to previous window for smooth transition
        previous_window = self.current_window
            
        # Ensure kiosk mode is consistent when switching windows
        if previous_window and previous_window.is_kiosk_mode and not window.is_kiosk_mode:
            # If we're coming from a window in kiosk mode, make sure the new window is also in kiosk mode
            logger.info(f"Setting {window_name} to kiosk mode to match current window state")
            window.is_kiosk_mode = True
            
            # Apply kiosk mode UI changes
            window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            
            # Use the method to update all components consistently
            window._update_kiosk_mode_in_components()
        
        # Make sure theme is up to date before showing the window
        if hasattr(self, 'current_theme_is_dark'):
            if window.is_dark_mode != self.current_theme_is_dark:
                self._apply_theme_to_window(window, self.current_theme_is_dark)
        
        # Update current window references before showing the new window
        self.current_window_name = window_name
        self.current_window = window
        
        # Prepare the new window but don't show it yet if we have a previous window
        if previous_window:
            # Match geometry exactly before showing to ensure full overlap
            if window.is_kiosk_mode:
                # For kiosk mode, make sure we're using the full screen geometry
                screen = previous_window.screen()
                window.setGeometry(screen.geometry())
            else:
                # For normal windows, match the geometry exactly to prevent "bumping"
                window.setGeometry(previous_window.geometry())
            
            # IMPORTANT: We need both windows to be fully visible and stacked properly
            # before starting any opacity changes. The previous window is already visible.
            
            # Ensure the new window is fully prepped and ready
            window.setWindowOpacity(0.0)  # Start completely transparent
            window.show()
            window.raise_()              # Make sure new window is on top
            
            # Let the event loop process the window stacking before animations
            QTimer.singleShot(10, lambda: self._start_fade_transition(window, previous_window))
        else:
            # If there's no previous window, just show the new one immediately
            window.show()
            
            # If window should be in kiosk mode, make sure it's in full screen
            if window.is_kiosk_mode:
                logger.info(f"Ensuring {window_name} is in full screen")
                window.showFullScreen()
        
        # Update rotation index
        if window_name in self.rotation_order:
            self.rotation_index = self.rotation_order.index(window_name)
            
        # Emit signal
        self.window_changed.emit(window_name)
        logger.info(f"Changed active window to: {window_name}")
        
        # Update last used time for the window (using timestamp in milliseconds)
        self.window_last_used[window_name] = int(time.time() * 1000)
    
    def _start_fade_transition(self, new_window, previous_window):
        """Start a pure cross-fade transition between windows"""
        # If window should be in kiosk mode, make sure it's in full screen
        if new_window.is_kiosk_mode:
            logger.info(f"Ensuring {new_window.objectName() or 'window'} is in full screen")
            new_window.showFullScreen()
        
        # Activate the new window to ensure it has focus
        new_window.activateWindow()
        
        # Create a parallel animation group to ensure both animations run in sync
        fade_duration = 400  # milliseconds
        
        # Create fade-in animation for new window
        self.fade_in_animation = QPropertyAnimation(new_window, b"windowOpacity")
        self.fade_in_animation.setDuration(fade_duration)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Create fade-out animation for previous window
        self.fade_out_animation = QPropertyAnimation(previous_window, b"windowOpacity")
        self.fade_out_animation.setDuration(fade_duration)
        self.fade_out_animation.setStartValue(1.0) 
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Hide the previous window when its animation is done
        self.fade_out_animation.finished.connect(lambda: self._finalize_transition(previous_window))
        
        # Start both animations
        self.fade_in_animation.start()
        self.fade_out_animation.start()
    
    def _finalize_transition(self, window):
        """Finalize the transition by hiding the window after it's already invisible"""
        # Hide the window now that it's invisible (opacity 0)
        window.hide()
        # Reset opacity for future use
        window.setWindowOpacity(1.0)
    
    def rotate_to_next_window(self):
        """Rotate to the next window in the rotation order"""
        # Only rotate if rotation is enabled and current window is in kiosk mode
        if not self.rotation_enabled or not self.current_window or not self.current_window.is_kiosk_mode:
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
        # Store the current theme state so we can apply it to windows when they become visible
        self.current_theme_is_dark = is_dark_mode
        
        # Only update visible windows immediately
        for window in self.windows.values():
            if window.isVisible():
                self._apply_theme_to_window(window, is_dark_mode)
            else:
                # For hidden windows, just store the theme state
                # Theme will be applied when the window becomes visible
                window.is_dark_mode = is_dark_mode
                window.colors = DARK_COLORS if is_dark_mode else LIGHT_COLORS
                
    def _apply_theme_to_window(self, window, is_dark_mode):
        """Apply theme changes to a specific window"""
        if window.is_dark_mode != is_dark_mode:
            window.is_dark_mode = is_dark_mode
            window.colors = DARK_COLORS if is_dark_mode else LIGHT_COLORS
            window.apply_styling()
            
            # If the window is a Themeable, use the update_theme method
            if isinstance(window, Themeable):
                window.update_theme(is_dark_mode, window.colors)
            # Fallback to legacy methods for backward compatibility
            elif hasattr(window, '_update_theme_in_components'):
                window._update_theme_in_components()
            elif hasattr(window, 'handle_theme_changed'):
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
            # Only start the timer if not already active
            if not self.rotation_timer.isActive():
                self.rotation_timer.start(self.rotation_interval)
                logger.info(f"Started rotation timer with interval {self.rotation_interval}ms")
        else:
            # Only stop the timer if it's active
            if self.rotation_timer.isActive():
                self.rotation_timer.stop()
                logger.info("Stopped rotation timer")
    
    def _register_task(self, task):
        """Add a task to the pending tasks set and set up its cleanup callback."""
        self._pending_tasks.add(task)
        task.add_done_callback(self._remove_task)
        return task
    
    def _remove_task(self, task):
        """Remove a completed task from the pending tasks set."""
        self._pending_tasks.discard(task)
    
    def _cancel_pending_tasks(self):
        """Cancel all pending tasks created by this manager."""
        for task in list(self._pending_tasks):
            if not task.done():
                logger.info(f"Cancelling pending task: {task}")
                task.cancel()
                
    async def _await_task_with_timeout(self, coro, timeout=2.0):
        """Run a coroutine as a task with timeout and exception handling."""
        task = self._register_task(asyncio.create_task(coro))
        try:
            return await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Task timed out after {timeout}s: {coro.__qualname__}")
            return None
        except asyncio.CancelledError:
            logger.debug(f"Task was cancelled: {coro.__qualname__}")
            return None
        except Exception as e:
            logger.error(f"Task failed with exception: {e}")
            return None
    
    def check_for_windows_to_unload(self):
        """Check for windows that have been inactive for a while and unload them to free memory"""
        if not self.memory_optimization_enabled:
            return
            
        # Get current time in milliseconds
        current_time = int(time.time() * 1000)
        windows_to_unload = []
        
        for window_name, window in self.windows.items():
            # Never unload the current window
            if window_name == self.current_window_name:
                continue
                
            # Skip windows that are visible
            if window.isVisible():
                continue
                
            # Check if the window has been inactive for long enough
            last_used = self.window_last_used.get(window_name, 0)
            if current_time - last_used > self.inactive_window_timeout:
                windows_to_unload.append(window_name)
        
        # Unload the windows
        for window_name in windows_to_unload:
            self.unload_window(window_name)
    
    def unload_window(self, window_name):
        """Unload a window to free memory"""
        if window_name not in self.windows:
            return
            
        logger.info(f"Unloading inactive window: {window_name}")
        
        # Get the window object
        window = self.windows[window_name]
        
        # Remove it from our tracking dictionaries
        del self.windows[window_name]
        if window_name in self.window_last_used:
            del self.window_last_used[window_name]
            
        # Clean up the window
        window.deleteLater()
    
    def set_memory_optimization(self, enabled, timeout_ms=None):
        """Enable or disable memory optimization by unloading inactive windows"""
        self.memory_optimization_enabled = enabled
        
        if timeout_ms is not None:
            self.inactive_window_timeout = max(timeout_ms, 60000)  # Minimum 1 minute
            
        logger.info(f"Memory optimization {'enabled' if enabled else 'disabled'} " 
                   f"with timeout {self.inactive_window_timeout}ms")

    async def cleanup(self):
        """Clean up resources before shutdown"""
        logger.info("Cleaning up WindowManager")
        
        # Stop timers
        self.rotation_timer.stop()
        self.window_unload_timer.stop()
        
        # Get list of all windows to clean up (make a copy to avoid modification during iteration)
        windows_to_cleanup = list(self.windows.items())
        
        # Track all cleanup tasks
        cleanup_tasks = []
        
        # Close and clean up all windows
        for name, window in windows_to_cleanup:
            logger.info(f"Cleaning up window: {name}")
            
            # Special handling for ChatWindow - run cleanup tasks concurrently
            if name == "chat" and hasattr(window, "controller"):
                logger.info("Cleaning up chat controller")
                
                # Handle async cleanup with proper task awaiting
                try:
                    if hasattr(window.controller, "cleanup"):
                        if asyncio.iscoroutinefunction(window.controller.cleanup):
                            # Create the task and add it to our cleanup tasks, but don't await yet
                            cleanup_task = self._register_task(
                                asyncio.create_task(window.controller.cleanup())
                            )
                            cleanup_tasks.append(cleanup_task)
                        else:
                            # Call directly if it's synchronous
                            window.controller.cleanup()
                except Exception as e:
                    logger.error(f"Error during controller cleanup: {e}")
            
            # Close the window
            logger.info(f"Closing window: {name}")
            window.close()
        
        # Wait for all cleanup tasks to finish with a timeout, but gather them for concurrent execution
        if cleanup_tasks:
            logger.info(f"Waiting for {len(cleanup_tasks)} cleanup tasks to complete")
            try:
                # Use asyncio.gather with return_exceptions=True to prevent exceptions from stopping
                # all tasks, but with a timeout to avoid waiting indefinitely
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=2.0  # 2 seconds max wait time
                )
            except asyncio.TimeoutError:
                logger.warning(f"Cleanup tasks did not complete within timeout")
            except Exception as e:
                logger.error(f"Error during cleanup tasks: {e}")
        
        # Cancel our own pending tasks (not all tasks in the event loop)
        self._cancel_pending_tasks()
            
        logger.info("WindowManager cleanup complete") 
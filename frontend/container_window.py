#!/usr/bin/env python3
"""
ContainerWindow - A single window that manages transitions between different screens.
This approach avoids the desktop background visibility issues during transitions
by keeping everything within a single window.
"""

import asyncio
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QStackedWidget, QLabel, QMenu, QDialog,
    QGroupBox, QFormLayout, QComboBox, QSpinBox, QDialogButtonBox
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QPropertyAnimation, 
    QParallelAnimationGroup, QEasingCurve, QEvent
)
from typing import Dict, Type, Optional, List

from frontend.config import logger
from frontend.style import DARK_COLORS, LIGHT_COLORS, load_stylesheet
from frontend.themeable import Themeable
from frontend.screen_manager import ScreenManager
from frontend.screen_widget import ScreenWidget
from frontend.performance_monitor import PerformanceMonitor
from frontend.transitions import TransitionType

# Import screen implementations
from frontend.clock_widget import ClockScreen  # Implemented real ClockScreen
from frontend.chat_widget import ChatScreen    # Implemented real ChatScreen

class TransitionSettingsDialog(QDialog):
    """Dialog for configuring transition settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transition Settings")
        self.setMinimumWidth(400)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Create transition type group
        type_group = QGroupBox("Default Transition Type")
        type_layout = QFormLayout(type_group)
        
        # Transition type dropdown
        self.transition_type = QComboBox()
        for t in TransitionType:
            self.transition_type.addItem(t.name, t)
        type_layout.addRow("Transition Type:", self.transition_type)
        
        # Animation settings group
        anim_group = QGroupBox("Animation Settings")
        anim_layout = QFormLayout(anim_group)
        
        # Duration spinner
        self.duration = QSpinBox()
        self.duration.setRange(100, 2000)
        self.duration.setSingleStep(50)
        self.duration.setSuffix(" ms")
        self.duration.setValue(400)
        anim_layout.addRow("Duration:", self.duration)
        
        # Easing curve dropdown
        self.easing_curve = QComboBox()
        for name in dir(QEasingCurve.Type):
            if not name.startswith('_') and name != 'Custom':
                self.easing_curve.addItem(name, getattr(QEasingCurve.Type, name))
        self.easing_curve.setCurrentText("InOutQuad")
        anim_layout.addRow("Easing Curve:", self.easing_curve)
        
        # Add groups to main layout
        layout.addWidget(type_group)
        layout.addWidget(anim_group)
        
        # Add buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_settings(self):
        """Get the selected settings."""
        return {
            'transition_type': self.transition_type.currentData(),
            'duration': self.duration.value(),
            'easing_curve': self.easing_curve.currentData()
        }

class ContainerWindow(QMainWindow):
    """
    Main container window that holds all screens and manages transitions.
    This is the only top-level window in the application.
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Display")
        self.setMinimumSize(800, 600)
        
        # Initialize state
        self.is_dark_mode = True
        self.is_kiosk_mode = False
        self.previous_geometry = None
        
        # Create central widget with stacked layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Create stacked widget to hold all screens
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        
        # Ensure stacked widget has a solid background
        self.stacked_widget.setAutoFillBackground(True)
        
        # Initialize performance monitor
        self.performance_monitor = PerformanceMonitor(self)
        
        # Create the screen manager
        self.screen_manager = ScreenManager(self.stacked_widget, self)
        
        # Set up animation properties for transitions
        self.setup_animations()
        
        # Register available screens
        self.register_screens()
        
        # Apply initial styling
        self.apply_styling()
        
        # Create the context menu
        self.create_context_menu()
        
        # Connect signals
        self.connect_signals()
        
        # Start performance monitoring
        self.performance_monitor.start_monitoring()
        
        # Install event filter to catch keyboard shortcuts globally
        self.installEventFilter(self)
    
    def setup_animations(self):
        """Set up animation properties for transitions."""
        # Set up animation for screen transitions
        self.fade_duration = 400  # milliseconds
        self.easing_curve = QEasingCurve.Type.InOutQuad
    
    def register_screens(self):
        """Register all available screen types with the manager."""
        # Register screen types - now using the real implementations
        self.screen_manager.register_screen_type("clock", ClockScreen, "Clock")
        self.screen_manager.register_screen_type("chat", ChatScreen, "Chat")
        
        # Set up custom navigation between screens if needed
        # This adds navigation buttons to all screens
        for screen_name, display_name in [("clock", "Clock"), ("chat", "Chat")]:
            # Register in rotation order (if not already registered)
            if screen_name not in self.screen_manager.rotation_order:
                self.screen_manager.rotation_order.append(screen_name)
    
    def create_context_menu(self):
        """Create the context menu for the container window."""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Create the context menu
        self.context_menu = QMenu(self)
        
        # Theme actions
        self.theme_menu = QMenu("Theme", self)
        self.theme_action_light = self.theme_menu.addAction("Light")
        self.theme_action_dark = self.theme_menu.addAction("Dark")
        self.theme_action_light.triggered.connect(lambda: self.set_theme(False))
        self.theme_action_dark.triggered.connect(lambda: self.set_theme(True))
        self.context_menu.addMenu(self.theme_menu)
        
        # Kiosk mode action
        self.kiosk_action = self.context_menu.addAction("Toggle Kiosk Mode")
        self.kiosk_action.triggered.connect(self.toggle_kiosk_mode)
        
        # Screens submenu
        self.screens_menu = QMenu("Screens", self)
        self.context_menu.addMenu(self.screens_menu)
        
        # Performance submenu
        self.performance_menu = QMenu("Performance", self)
        self.show_performance_action = self.performance_menu.addAction("Show Performance Summary")
        self.show_performance_action.triggered.connect(self.show_performance_summary)
        self.context_menu.addMenu(self.performance_menu)
        
        # Transition settings
        self.transition_menu = QMenu("Transitions", self)
        
        # Add transition type options
        for t in TransitionType:
            action = self.transition_menu.addAction(f"Use {t.name}")
            # Use lambda with default arg to capture the current value of t
            action.triggered.connect(lambda checked, type=t: self.set_transition_type(type))
        
        self.transition_menu.addSeparator()
        self.transition_settings_action = self.transition_menu.addAction("Transition Settings...")
        self.transition_settings_action.triggered.connect(self.show_transition_settings)
        
        self.context_menu.addMenu(self.transition_menu)
    
    def show_context_menu(self, pos):
        """Show the context menu at the specified position."""
        # Update the screens submenu with current screens
        self.screens_menu.clear()
        for screen_name in self.screen_manager.screen_types.keys():
            display_name = self.screen_manager.screen_display_names.get(screen_name, screen_name.title())
            action = self.screens_menu.addAction(display_name)
            # Use lambda with default arg to capture the current value of screen_name
            action.triggered.connect(lambda checked, name=screen_name: self.screen_manager.show_screen(name))
            
            # Add indicator for current screen
            if screen_name == self.screen_manager.current_screen_name:
                action.setCheckable(True)
                action.setChecked(True)
        
        # Show the context menu
        self.context_menu.exec(self.mapToGlobal(pos))
    
    def set_theme(self, is_dark):
        """Set the theme to light or dark."""
        if self.is_dark_mode != is_dark:
            self.is_dark_mode = is_dark
            self.apply_styling()
    
    def set_transition_type(self, transition_type):
        """Set the default transition type."""
        logger.info(f"Setting default transition to: {transition_type.name}")
        self.screen_manager.set_default_transition(transition_type)
    
    def show_transition_settings(self):
        """Show the transition settings dialog."""
        dialog = TransitionSettingsDialog(self)
        
        # Set current values
        dialog.transition_type.setCurrentText(self.screen_manager.default_transition_type.name)
        dialog.duration.setValue(self.screen_manager.transition_manager.duration)
        
        # Find easing curve in combo box
        for i in range(dialog.easing_curve.count()):
            if dialog.easing_curve.itemData(i) == self.screen_manager.transition_manager.easing_curve:
                dialog.easing_curve.setCurrentIndex(i)
                break
        
        # Show dialog and apply settings if accepted
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            self.screen_manager.set_default_transition(settings['transition_type'])
            self.screen_manager.set_transition_duration(settings['duration'])
            self.screen_manager.set_transition_easing(settings['easing_curve'])
    
    def connect_signals(self):
        """Connect signals for handling screen changes and theme changes."""
        # Connect screen manager signals
        self.screen_manager.screen_changed.connect(self.handle_screen_changed)
        self.screen_manager.pre_screen_change.connect(self.handle_pre_screen_change)
        self.screen_manager.post_screen_change.connect(self.handle_post_screen_change)
        
        # Connect performance monitor signals
        self.performance_monitor.metrics_updated.connect(self.handle_metrics_updated)
    
    def handle_screen_changed(self, screen_name):
        """Handle when the active screen changes."""
        # Update window title to reflect current screen
        display_name = self.screen_manager.screen_display_names.get(screen_name, screen_name.title())
        self.setWindowTitle(f"Smart Display - {display_name}")
    
    def handle_pre_screen_change(self, from_screen, to_screen):
        """Handle the beginning of a screen transition"""
        # Start timing the transition
        self.performance_monitor.start_transition_timer(from_screen, to_screen)
    
    def handle_post_screen_change(self, from_screen, to_screen):
        """Handle the end of a screen transition"""
        # Stop timing the transition
        transition_time = self.performance_monitor.stop_transition_timer()
        
        # If transition time is too long, log a warning
        if transition_time and transition_time > 500:  # 500ms threshold
            logger.warning(f"Slow transition detected: {transition_time}ms from {from_screen} to {to_screen}")
    
    def handle_metrics_updated(self, metrics):
        """Handle updated performance metrics"""
        # Check for concerning memory usage
        if metrics.get('memory', {}).get('percent', 0) > 90:
            logger.warning("High memory usage detected: %.1f%%" % metrics['memory']['percent'])
            
            # Suggest memory optimization if not already enabled
            if not self.screen_manager.memory_optimization_enabled:
                logger.info("Enabling memory optimization due to high memory usage")
                self.screen_manager.set_memory_optimization(True, 180000)  # 3 minutes timeout
        
        # Check for concerning CPU usage
        if metrics.get('cpu', {}).get('percent', 0) > 80:
            logger.warning("High CPU usage detected: %.1f%%" % metrics['cpu']['percent'])
    
    def apply_styling(self):
        """Apply stylesheet to the application."""
        stylesheet = load_stylesheet(self.is_dark_mode)
        self.setStyleSheet(stylesheet)
        
        # Make sure stacked widget has a solid background color
        bg_color = DARK_COLORS["background"] if self.is_dark_mode else LIGHT_COLORS["background"]
        self.stacked_widget.setStyleSheet(f"QStackedWidget {{ background-color: {bg_color}; }}")
        
        # Apply background color to the central widget too
        self.central_widget.setStyleSheet(f"background-color: {bg_color};")
        
        # Ensure all screens have proper background
        for screen_name, screen in self.screen_manager.screens.items():
            if hasattr(screen, 'setAutoFillBackground'):
                screen.setAutoFillBackground(True)
        
        # Update theme in all screens via the screen manager
        self.screen_manager.handle_theme_changed(self.is_dark_mode)
    
    def toggle_theme(self):
        """Toggle between light and dark themes."""
        self.is_dark_mode = not self.is_dark_mode
        
        # Apply the new theme
        self.apply_styling()
    
    def toggle_kiosk_mode(self):
        """Toggle fullscreen/kiosk mode."""
        # Save current state before toggling
        was_kiosk_mode = self.is_kiosk_mode
        self.is_kiosk_mode = not was_kiosk_mode
        
        logger.info(f"Toggling kiosk mode to {self.is_kiosk_mode}")
        
        # Store current geometry before changing window state if not already stored
        if not was_kiosk_mode:
            self.previous_geometry = self.geometry()
        
        if self.is_kiosk_mode:
            # Enter kiosk mode
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            
            # Get background color based on theme
            bg_color = DARK_COLORS["background"] if self.is_dark_mode else LIGHT_COLORS["background"]
            
            # Use a simpler approach to ensure solid background
            self.setAutoFillBackground(True)
            self.central_widget.setAutoFillBackground(True)
            self.stacked_widget.setAutoFillBackground(True)
            
            # Apply solid background to important widgets
            solid_bg_style = f"""
                QMainWindow, QStackedWidget {{ 
                    background-color: {bg_color}; 
                }}
            """
            
            # Apply the style as an addition, not replacing the entire stylesheet
            current_style = self.styleSheet()
            self.setStyleSheet(current_style + solid_bg_style)
            
            # Show and go fullscreen
            self.show()
            self.showFullScreen()
        else:
            # Exit kiosk mode
            self.setWindowFlags(Qt.WindowType.Window)
            
            # Restore original styling
            self.apply_styling()
            
            self.show()
            self.showNormal()
            
            # Restore previous geometry if available
            if self.previous_geometry:
                self.setGeometry(self.previous_geometry)
        
        # Update kiosk mode in all screens via the screen manager
        for screen_name, screen in self.screen_manager.screens.items():
            if hasattr(screen, 'set_kiosk_mode'):
                screen.set_kiosk_mode(self.is_kiosk_mode)
    
    def eventFilter(self, watched, event):
        """
        Global event filter to catch keyboard shortcuts regardless of focus.
        This ensures that keyboard shortcuts work even when child widgets have focus.
        """
        if event.type() == QEvent.Type.KeyPress:
            # Log all key presses for debugging - MUCH MORE VERBOSE
            raw_key = event.key()
            modifiers = event.modifiers()
            logger.info(f"URGENT DEBUG - Key press intercepted by event filter: key={raw_key}, mods={modifiers}, text='{event.text()}'")
            logger.info(f"URGENT DEBUG - Qt.Key_1={Qt.Key.Key_1}, Ctrl mod={Qt.KeyboardModifier.ControlModifier}")
            
            # MORE AGGRESSIVE APPROACH - Handle all Ctrl+number combinations
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                logger.info(f"URGENT DEBUG - Ctrl modifier detected!")
                
                # Check for number keys 1-9
                for i in range(1, 10):
                    if raw_key == getattr(Qt.Key, f"Key_{i}"):
                        logger.info(f"URGENT DEBUG - Ctrl+{i} detected!")
                        # Get transition types and safely set the type
                        transition_types = list(TransitionType)
                        index = i - 1
                        if index < len(transition_types):
                            transition_type = transition_types[index]
                            logger.info(f"URGENT DEBUG - Setting transition to {transition_type.name}")
                            self.set_transition_type(transition_type)
                        return True  # Event handled
                
                # Check for Ctrl+P
                if raw_key == Qt.Key.Key_P:
                    logger.info("URGENT DEBUG - Ctrl+P detected!")
                    self.show_performance_summary()
                    return True
            
            # Check for Alt+T
            if (modifiers & Qt.KeyboardModifier.AltModifier) and raw_key == Qt.Key.Key_T:
                logger.info("URGENT DEBUG - Alt+T detected!")
                self.show_transition_settings()
                return True
            
            # ESC key behavior
            if raw_key == Qt.Key.Key_Escape:
                logger.info("URGENT DEBUG - ESC key detected!")
                self.toggle_kiosk_mode()
                return True  # Event handled
        
        # Continue with normal event processing for unhandled events
        return super().eventFilter(watched, event)
    
    # We'll keep the original keyPressEvent for backward compatibility, but it's less likely to be triggered
    def keyPressEvent(self, event):
        """Handle key press events."""
        logger.info(f"Regular keyPressEvent (may not be triggered): {event.key()}")
        super().keyPressEvent(event)
    
    def show_performance_summary(self):
        """Display a summary of performance metrics"""
        summary = self.performance_monitor.get_metrics_summary()
        
        if not summary.get('memory_avg'):
            logger.info("No performance data available yet")
            return
            
        logger.info(f"=== Performance Summary ===")
        logger.info(f"Memory usage: {summary['memory_avg']:.1f}% avg, {summary['memory_max']:.1f}% max")
        logger.info(f"CPU usage: {summary['cpu_avg']:.1f}% avg, {summary['cpu_max']:.1f}% max")
        if summary.get('fps_avg'):
            logger.info(f"Frame rate: {summary['fps_avg']:.1f} FPS average")
        logger.info(f"==========================")
    
    async def cleanup(self):
        """Clean up resources before shutdown."""
        # Stop performance monitoring
        self.performance_monitor.stop_monitoring()
        
        # Run cleanup on the screen manager
        await self.screen_manager.cleanup()


# Function to initialize and show the container window
def create_container_window():
    """Create and return a new container window instance."""
    window = ContainerWindow()
    window.show()
    
    # Initialize the screen manager with chat as the starting screen
    window.screen_manager.initialize("chat")  # Start with chat screen as the main screen
    
    return window 
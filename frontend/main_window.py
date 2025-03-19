#!/usr/bin/env python3
import sys
import asyncio
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QPushButton, QVBoxLayout, QToolBar, QSizePolicy
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

from frontend.config import logger
from frontend.style import DARK_COLORS, LIGHT_COLORS, generate_main_stylesheet
from frontend.screen_manager import ScreenManager
from frontend.screens.chat_screen import ChatScreen
from frontend.screens.clock_screen import ClockScreen
from frontend.screens.weather_screen import WeatherScreen
from frontend.screens.photos_screen import PhotosScreen
from frontend.screens.settings_screen import SettingsScreen

class MainWindow(QMainWindow):
    """
    Main application window that hosts all screens and implements kiosk mode.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Display")
        self.setMinimumSize(800, 600)
        
        # Initialize state
        self.is_dark_mode = True
        self.colors = DARK_COLORS
        # Always start in kiosk mode
        self.is_kiosk_mode = True
        
        # Setup UI components
        self.setup_ui()
        
        # Initial theme setup
        self.update_theme_icon()
        
        # Enable kiosk mode on startup
        self.enable_kiosk_mode()
    
    def setup_ui(self):
        """Setup the UI components"""
        # Create central widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create top toolbar
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setFixedHeight(50)
        self.toolbar.setStyleSheet("""
            QToolBar {
                spacing: 5px;
                border: none;
            }
        """)
        
        # Create screen menu container for left side
        self.screen_menu_container = QWidget()
        screen_menu_layout = QHBoxLayout(self.screen_menu_container)
        screen_menu_layout.setContentsMargins(10, 0, 0, 0)
        screen_menu_layout.setSpacing(5)
        screen_menu_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # Create main menu container for right side
        self.main_menu_container = QWidget()
        main_menu_layout = QHBoxLayout(self.main_menu_container)
        main_menu_layout.setContentsMargins(0, 0, 10, 0)
        main_menu_layout.setSpacing(5)
        main_menu_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Create menu buttons - right side
        self.clock_button = self.create_menu_button("clock", "Clock")
        self.weather_button = self.create_menu_button("weather", "Weather")
        self.photos_button = self.create_menu_button("photos", "Photos")
        self.settings_button = self.create_menu_button("settings", "Settings")
        self.chat_button = self.create_menu_button("chat", "Chat")
        
        # Add buttons to main menu layout (right side)
        main_menu_layout.addWidget(self.clock_button)
        main_menu_layout.addWidget(self.weather_button)
        main_menu_layout.addWidget(self.photos_button)
        main_menu_layout.addWidget(self.settings_button)
        main_menu_layout.addWidget(self.chat_button)
        
        # Create theme toggle button
        self.theme_button = QPushButton()
        self.theme_button.setFixedSize(45, 45)
        self.theme_button.setIcon(QIcon("frontend/icons/dark_mode.svg"))
        self.theme_button.setIconSize(QSize(35, 35))
        self.theme_button.clicked.connect(self.toggle_theme)
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
        main_menu_layout.addWidget(self.theme_button)
        
        # Add containers to toolbar
        self.toolbar.addWidget(self.screen_menu_container)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        self.toolbar.addWidget(self.main_menu_container)
        
        # Create screen manager
        self.screen_manager = ScreenManager(self.colors)
        
        # Add screens
        self.chat_screen = ChatScreen(self.colors)
        self.clock_screen = ClockScreen(self.colors)
        self.weather_screen = WeatherScreen(self.colors)
        self.photos_screen = PhotosScreen(self.colors)
        self.settings_screen = SettingsScreen(self.colors)
        
        self.screen_manager.add_screen("chat", self.chat_screen)
        self.screen_manager.add_screen("clock", self.clock_screen)
        self.screen_manager.add_screen("weather", self.weather_screen)
        self.screen_manager.add_screen("photos", self.photos_screen)
        self.screen_manager.add_screen("settings", self.settings_screen)
        
        # Set initial screen
        self.screen_manager.set_current_screen("clock")
        
        # Add components to main layout
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.screen_manager, 1)
        
        # Connect screen manager signals
        self.screen_manager.theme_changed.connect(self.update_theme)
        self.screen_manager.screen_changed.connect(self.handle_screen_changed)
        
        # Connect menu buttons
        self.chat_button.clicked.connect(lambda: self.screen_manager.set_current_screen("chat"))
        self.clock_button.clicked.connect(lambda: self.screen_manager.set_current_screen("clock"))
        self.weather_button.clicked.connect(lambda: self.screen_manager.set_current_screen("weather"))
        self.photos_button.clicked.connect(lambda: self.screen_manager.set_current_screen("photos"))
        self.settings_button.clicked.connect(lambda: self.screen_manager.set_current_screen("settings"))
        
        # Connect settings screen signals
        self.settings_screen.settings_changed.connect(self.handle_settings_changed)
    
    def create_menu_button(self, icon_name, tooltip):
        """Create a menu button with the given icon and tooltip"""
        button = QPushButton()
        button.setFixedSize(45, 45)
        button.setIcon(QIcon(f"frontend/icons/{icon_name}.svg"))
        button.setIconSize(QSize(30, 30))
        button.setToolTip(tooltip)
        button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        
        return button
    
    def toggle_theme(self):
        """Toggle between light and dark theme"""
        self.is_dark_mode = not self.is_dark_mode
        self.colors = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS
        self.update_theme_icon()
        self.apply_styling()
        self.screen_manager.update_colors(self.colors)
    
    def update_theme(self, is_dark_mode):
        """Update theme based on screen manager signal"""
        self.is_dark_mode = is_dark_mode
        self.colors = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS
        self.update_theme_icon()
        self.apply_styling()
    
    def update_theme_icon(self):
        """Update the theme button icon based on current theme"""
        icon_name = "light_mode" if self.is_dark_mode else "dark_mode"
        self.theme_button.setIcon(QIcon(f"frontend/icons/{icon_name}.svg"))
    
    def apply_styling(self):
        """Apply styling to all components"""
        self.setStyleSheet(generate_main_stylesheet(self.colors))
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key.Key_Escape:
            # ESC key terminates the application
            logger.info("ESC key pressed - terminating application")
            self.close()
        super().keyPressEvent(event)
    
    def enable_kiosk_mode(self):
        """Enable kiosk mode (fullscreen without window decorations)"""
        # Hide window frame first
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        # Show the window after changing flags
        self.show()
        # Enable fullscreen - must be called after show() to ensure it takes effect immediately
        self.showFullScreen()
    
    def handle_settings_changed(self, settings):
        """Handle settings changes from the settings screen"""
        logger.info(f"Settings changed: {settings}")
        
        # Handle auto rotation setting
        if settings["auto_rotation"]:
            self.screen_manager.start_rotation(settings["rotation_interval"] * 1000)
        else:
            self.screen_manager.stop_rotation()
    
    def handle_screen_changed(self, screen_name):
        """Handle screen changes and update menu accordingly"""
        logger.info(f"Screen changed to: {screen_name}")
        
        # Clear the screen menu container first
        layout = self.screen_menu_container.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        
        # If chat screen is active, move its menu to the left
        if screen_name == "chat":
            # Get the chat screen's top buttons and move them to our container
            chat_top_buttons = self.chat_screen.top_buttons
            
            # Ensure it's not already in another layout
            if chat_top_buttons.parent() is not None:
                chat_top_buttons.setParent(None)
                
            # Add to our container
            layout.addWidget(chat_top_buttons)
            
            # Make sure the chat screen knows its top buttons have been moved
            self.chat_screen.top_buttons_moved = True
        
        # Update the UI
        self.screen_menu_container.update()
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Closing application...")
        # Clean up all screens
        self.chat_screen.cleanup()
        super().closeEvent(event)

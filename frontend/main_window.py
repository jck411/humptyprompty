#!/usr/bin/env python3
import sys
import asyncio
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QPushButton, QVBoxLayout
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

from frontend.config import logger
from frontend.style import DARK_COLORS, LIGHT_COLORS, generate_main_stylesheet
from frontend.screen_manager import ScreenManager
from frontend.screens.chat_screen import ChatScreen

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
        self.is_kiosk_mode = False
        
        # Setup UI components
        self.setup_ui()
        
        # Initial theme setup
        self.update_theme_icon()
    
    def setup_ui(self):
        """Setup the UI components"""
        # Create central widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create menu bar
        self.menu_bar = QWidget()
        self.menu_bar.setFixedHeight(50)
        menu_layout = QHBoxLayout(self.menu_bar)
        menu_layout.setContentsMargins(10, 5, 10, 5)
        
        # Create menu buttons
        self.chat_button = self.create_menu_button("chat", "Chat")
        self.clock_button = self.create_menu_button("clock", "Clock")
        self.weather_button = self.create_menu_button("weather", "Weather")
        self.photos_button = self.create_menu_button("photos", "Photos")
        
        # Add stretch to push theme button to the right
        menu_layout.addStretch()
        
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
        menu_layout.addWidget(self.theme_button)
        
        # Create screen manager
        self.screen_manager = ScreenManager(self.colors)
        
        # Add screens
        self.chat_screen = ChatScreen(self.colors)
        self.screen_manager.add_screen("chat", self.chat_screen)
        
        # Set initial screen
        self.screen_manager.set_current_screen("chat")
        
        # Add components to main layout
        main_layout.addWidget(self.menu_bar)
        main_layout.addWidget(self.screen_manager, 1)
        
        # Connect screen manager theme signal
        self.screen_manager.theme_changed.connect(self.update_theme)
        
        # Connect menu buttons
        self.chat_button.clicked.connect(lambda: self.screen_manager.set_current_screen("chat"))
    
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
        
        # Add to menu layout
        self.menu_bar.layout().addWidget(button)
        
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
            self.toggle_kiosk_mode()
        super().keyPressEvent(event)
    
    def toggle_kiosk_mode(self):
        """Toggle kiosk mode"""
        self.is_kiosk_mode = not self.is_kiosk_mode
        
        if self.is_kiosk_mode:
            # Enable fullscreen
            self.showFullScreen()
            # Hide window frame
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
            # Hide menu bar
            self.menu_bar.hide()
        else:
            # Disable fullscreen
            self.showNormal()
            # Restore window frame
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.FramelessWindowHint)
            # Show menu bar
            self.menu_bar.show()
            
        # Show the window after changing flags
        self.show()
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Closing application...")
        self.chat_screen.cleanup()
        super().closeEvent(event)
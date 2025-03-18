#!/usr/bin/env python3
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

from frontend.icons import (
    ICON_CLOCK, ICON_CHAT, ICON_WEATHER, 
    ICON_CALENDAR, ICON_PHOTO, ICON_SETTINGS
)

class BaseScreen(QWidget):
    """
    Base class for all screen widgets.
    Provides common functionality and lifecycle methods.
    """
    # Signals
    navigation_requested = pyqtSignal(str)  # Screen name to navigate to
    
    def __init__(self, name, colors):
        """
        Initialize the base screen
        
        Args:
            name: Unique name for this screen
            colors: Color scheme dictionary
        """
        super().__init__()
        self.setObjectName(name)
        self.screen_name = name
        self.colors = colors
        
        # Set up base layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)
        
        # Add navigation bar
        self.add_navigation_bar()
        
        # Initialize UI components
        self.setup_ui()
        
        # Apply initial styling
        self.apply_styling()
    
    def add_navigation_bar(self):
        """Add navigation bar to the top of the screen"""
        # Create navigation bar
        self.nav_bar = QWidget()
        self.nav_bar.setObjectName("nav_bar")
        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(15, 10, 15, 10)
        
        # Screen title
        self.title_label = QLabel(self.screen_name.capitalize())
        font = QFont("Arial", 16, QFont.Weight.Bold)
        self.title_label.setFont(font)
        
        # Navigation buttons with icons
        self.clock_button = QPushButton()
        self.clock_button.setIcon(ICON_CLOCK())
        self.clock_button.setToolTip("Clock")
        
        self.chat_button = QPushButton()
        self.chat_button.setIcon(ICON_CHAT())
        self.chat_button.setToolTip("Chat Assistant")
        
        self.weather_button = QPushButton()
        self.weather_button.setIcon(ICON_WEATHER())
        self.weather_button.setToolTip("Weather")
        
        self.calendar_button = QPushButton()
        self.calendar_button.setIcon(ICON_CALENDAR())
        self.calendar_button.setToolTip("Calendar")
        
        self.photo_button = QPushButton()
        self.photo_button.setIcon(ICON_PHOTO())
        self.photo_button.setToolTip("Photos")
        
        # Theme toggle button (using settings icon)
        self.settings_button = QPushButton("Theme")
        self.settings_button.setIcon(ICON_SETTINGS())
        self.settings_button.setToolTip("Toggle Light/Dark Theme")
        self.settings_button.setMinimumWidth(60)  # Make button wider to be more visible
        
        # Highlight current screen button
        if self.screen_name == "clock":
            self.clock_button.setProperty("current", True)
        elif self.screen_name == "chat":
            self.chat_button.setProperty("current", True)
        elif self.screen_name == "weather":
            self.weather_button.setProperty("current", True)
        elif self.screen_name == "calendar":
            self.calendar_button.setProperty("current", True)
        elif self.screen_name == "photo":
            self.photo_button.setProperty("current", True)
        
        # Connect navigation buttons
        self.clock_button.clicked.connect(lambda: self.navigate_to("clock"))
        self.chat_button.clicked.connect(lambda: self.navigate_to("chat"))
        self.weather_button.clicked.connect(lambda: self.navigate_to("weather"))
        self.calendar_button.clicked.connect(lambda: self.navigate_to("calendar"))
        self.photo_button.clicked.connect(lambda: self.navigate_to("photo"))
        # Direct implementation for theme toggle to bypass signal routing issues
        self.settings_button.clicked.connect(self.toggle_theme)
        
        # Add spacer to push buttons to the right
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        # Add widgets to layout
        nav_layout.addWidget(self.title_label)
        nav_layout.addItem(spacer)
        nav_layout.addWidget(self.clock_button)
        nav_layout.addWidget(self.chat_button)
        nav_layout.addWidget(self.weather_button)
        nav_layout.addWidget(self.calendar_button)
        nav_layout.addWidget(self.photo_button)
        nav_layout.addWidget(self.settings_button)
        
        # Add navigation bar to main layout
        self.layout.addWidget(self.nav_bar)
    
    def setup_ui(self):
        """
        Set up the UI components.
        Should be overridden by subclasses.
        """
        pass
    
    def apply_styling(self):
        """
        Apply styling to the screen.
        Can be overridden by subclasses.
        """
        self.setStyleSheet(f"""
            BaseScreen {{
                background-color: {self.colors['background']};
                color: {self.colors['text_primary']};
            }}
            QLabel {{
                color: {self.colors['text_primary']};
            }}
            QPushButton {{
                background-color: {self.colors['button_primary']};
                color: white;
                border: none;
                padding: 12px;
                border-radius: 10px;
                min-width: 48px;
                min-height: 48px;
                icon-size: 24px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['button_hover']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['button_pressed']};
            }}
            QPushButton[current="true"] {{
                background-color: {self.colors['button_pressed']};
                border: 2px solid white;
            }}
            #nav_bar {{
                background-color: {self.colors['background']};
                border-bottom: 1px solid {self.colors['input_border']};
            }}
        """)
    
    def update_colors(self, colors):
        """
        Update the color scheme
        
        Args:
            colors: New color scheme dictionary
        """
        self.colors = colors
        self.apply_styling()
    
    def on_activate(self):
        """
        Called when this screen becomes active.
        Should be overridden by subclasses to perform any necessary setup.
        """
        pass
    
    def on_deactivate(self):
        """
        Called when this screen becomes inactive.
        Should be overridden by subclasses to perform any necessary cleanup.
        """
        pass
    
    def navigate_to(self, screen_name):
        """
        Request navigation to another screen
        
        Args:
            screen_name: Name of the screen to navigate to
        """
        from frontend.config import logger
        logger.info(f"BaseScreen.navigate_to called with: {screen_name}")
        self.navigation_requested.emit(screen_name)
    
    def cleanup(self):
        """
        Clean up resources used by this screen.
        Should be overridden by subclasses to perform cleanup.
        Called when the application is closing.
        """
        pass 
        
    def toggle_theme(self):
        """
        Direct method to toggle the theme
        This is a workaround to bypass signal routing issues
        """
        from frontend.config import logger
        try:
            # Try to use the direct main_window reference first
            if hasattr(self, 'main_window'):
                logger.info("Using direct main_window reference to toggle theme")
                self.main_window.toggle_theme()
                return
                
            # Fallback to finding the main window through parent hierarchy
            main_window = self.window()
            logger.info(f"Directly calling toggle_theme on {main_window}")
            # Call the toggle_theme method on the main window
            if hasattr(main_window, 'toggle_theme'):
                main_window.toggle_theme()
            else:
                logger.error("Main window does not have toggle_theme method")
        except Exception as e:
            logger.error(f"Error toggling theme: {e}") 
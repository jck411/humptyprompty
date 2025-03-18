#!/usr/bin/env python3
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from frontend.base_screen import BaseScreen

class WeatherScreen(BaseScreen):
    """
    Screen that displays weather information.
    This is a placeholder implementation that would be connected to a weather API.
    """
    def __init__(self, colors):
        super().__init__(colors)
        
        # Setup UI components
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI components"""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create location label
        self.location_label = QLabel("New York, NY")
        self.location_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        location_font = QFont()
        location_font.setPointSize(36)
        location_font.setBold(True)
        self.location_label.setFont(location_font)
        
        # Create current weather widget
        current_weather = QWidget()
        current_layout = QHBoxLayout(current_weather)
        current_layout.setContentsMargins(0, 0, 0, 0)
        current_layout.setSpacing(20)
        current_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Weather icon (placeholder)
        self.weather_icon = QLabel()
        self.weather_icon.setFixedSize(100, 100)
        self.weather_icon.setPixmap(QIcon("frontend/icons/weather.svg").pixmap(100, 100))
        
        # Temperature and conditions
        temp_widget = QWidget()
        temp_layout = QVBoxLayout(temp_widget)
        temp_layout.setContentsMargins(0, 0, 0, 0)
        temp_layout.setSpacing(5)
        temp_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.temp_label = QLabel("72°F")
        temp_font = QFont()
        temp_font.setPointSize(48)
        temp_font.setBold(True)
        self.temp_label.setFont(temp_font)
        self.temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.conditions_label = QLabel("Partly Cloudy")
        conditions_font = QFont()
        conditions_font.setPointSize(24)
        self.conditions_label.setFont(conditions_font)
        self.conditions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        temp_layout.addWidget(self.temp_label)
        temp_layout.addWidget(self.conditions_label)
        
        current_layout.addWidget(self.weather_icon)
        current_layout.addWidget(temp_widget)
        
        # Create details widget
        details_widget = QWidget()
        details_layout = QHBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(40)
        details_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Humidity
        humidity_widget = QWidget()
        humidity_layout = QVBoxLayout(humidity_widget)
        humidity_layout.setContentsMargins(0, 0, 0, 0)
        humidity_layout.setSpacing(5)
        humidity_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        humidity_title = QLabel("Humidity")
        humidity_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.humidity_value = QLabel("45%")
        self.humidity_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        humidity_layout.addWidget(humidity_title)
        humidity_layout.addWidget(self.humidity_value)
        
        # Wind
        wind_widget = QWidget()
        wind_layout = QVBoxLayout(wind_widget)
        wind_layout.setContentsMargins(0, 0, 0, 0)
        wind_layout.setSpacing(5)
        wind_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        wind_title = QLabel("Wind")
        wind_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wind_value = QLabel("5 mph")
        self.wind_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        wind_layout.addWidget(wind_title)
        wind_layout.addWidget(self.wind_value)
        
        details_layout.addWidget(humidity_widget)
        details_layout.addWidget(wind_widget)
        
        # Add widgets to main layout
        main_layout.addWidget(self.location_label)
        main_layout.addWidget(current_weather)
        main_layout.addWidget(details_widget)
        
        # Apply initial styling
        self.update_colors(self.colors)
        
    def activate(self):
        """Called when the screen becomes active"""
        # In a real implementation, this would fetch weather data
        pass
        
    def deactivate(self):
        """Called when the screen is about to be hidden"""
        pass
        
    def update_colors(self, colors):
        """Update the color scheme"""
        super().update_colors(colors)
        
        # Update label colors
        text_color = f"color: {colors['text_primary']};"
        self.location_label.setStyleSheet(text_color)
        self.temp_label.setStyleSheet(text_color)
        self.conditions_label.setStyleSheet(text_color)
        
        # Find all QLabels and update their color
        for widget in self.findChildren(QLabel):
            widget.setStyleSheet(text_color)

#!/usr/bin/env python3
"""
Transition Test Script - Demonstrates all available screen transitions.
Provides a simple UI to test and compare different transition types.
"""

import os
import sys
import asyncio
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QComboBox, QSpinBox, QSlider,
    QRadioButton, QButtonGroup, QStackedWidget, QSplitter, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, QEasingCurve
from PyQt6.QtGui import QFont

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frontend.transitions import ScreenTransitionManager, TransitionType
from frontend.themeable import Themeable
from frontend.style import DARK_COLORS, LIGHT_COLORS, load_stylesheet
from frontend.config import logger

class ColorScreen(QWidget):
    """A simple colored screen for demonstrating transitions."""
    
    def __init__(self, color="#3b4261", parent=None):
        super().__init__(parent)
        self.color = color
        self.setAutoFillBackground(True)
        
        # Create layout with centered label
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Create label with screen info
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Arial", 24))
        self.label.setStyleSheet(f"color: white; background-color: transparent;")
        layout.addWidget(self.label)
        
        # Add some text to help visualize animations
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet("background-color: rgba(255, 255, 255, 0.2); color: white; border-radius: 10px;")
        self.text.setText("This is a sample screen to demonstrate transitions.\n\n"
                          "Each screen has a different color to make transitions easier to see.\n\n"
                          "Try different transition types to see the effects.")
        layout.addWidget(self.text)
        
        # Set background color
        self.setStyleSheet(f"background-color: {color};")
    
    def set_text(self, text):
        """Set the label text."""
        self.label.setText(text)

class TransitionTester(QMainWindow):
    """
    Test application for transitions between screens.
    Allows selection of transition type, duration, and easing curve.
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transition Tester")
        self.setMinimumSize(1000, 600)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create controls panel on the left
        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        
        # Create transition type selection
        type_group = QGroupBox("Transition Type")
        type_layout = QVBoxLayout(type_group)
        
        # Create radio buttons for each transition type
        self.transition_buttons = {}
        self.transition_group = QButtonGroup()
        
        for i, t in enumerate(TransitionType):
            radio = QRadioButton(t.name)
            self.transition_buttons[t] = radio
            self.transition_group.addButton(radio, i)
            type_layout.addWidget(radio)
            
            # Connect button to handler
            radio.clicked.connect(lambda checked, type=t: self.set_transition_type(type))
        
        # Select FADE by default
        self.transition_buttons[TransitionType.FADE].setChecked(True)
        self.current_transition = TransitionType.FADE
        
        controls_layout.addWidget(type_group)
        
        # Create duration control
        duration_group = QGroupBox("Duration (ms)")
        duration_layout = QVBoxLayout(duration_group)
        
        self.duration_slider = QSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(100, 2000)
        self.duration_slider.setValue(400)
        self.duration_slider.setTickInterval(100)
        self.duration_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        self.duration_label = QLabel("400 ms")
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        duration_layout.addWidget(self.duration_slider)
        duration_layout.addWidget(self.duration_label)
        
        # Connect slider to handler
        self.duration_slider.valueChanged.connect(self.duration_changed)
        
        controls_layout.addWidget(duration_group)
        
        # Create easing curve control
        easing_group = QGroupBox("Easing Curve")
        easing_layout = QVBoxLayout(easing_group)
        
        self.easing_combo = QComboBox()
        for name in dir(QEasingCurve.Type):
            if not name.startswith('_') and name != 'Custom':
                self.easing_combo.addItem(name, getattr(QEasingCurve.Type, name))
        self.easing_combo.setCurrentText("InOutQuad")
        
        easing_layout.addWidget(self.easing_combo)
        
        # Connect combo to handler
        self.easing_combo.currentIndexChanged.connect(self.easing_changed)
        
        controls_layout.addWidget(easing_group)
        
        # Create transition trigger button
        self.transition_button = QPushButton("Transition →")
        self.transition_button.setFixedHeight(50)
        self.transition_button.clicked.connect(self.trigger_transition)
        
        controls_layout.addWidget(self.transition_button)
        
        # Add auto-rotation option
        self.auto_button = QPushButton("Start Auto Rotation")
        self.auto_button.setCheckable(True)
        self.auto_button.clicked.connect(self.toggle_auto_rotation)
        
        controls_layout.addWidget(self.auto_button)
        
        # Add spacer
        controls_layout.addStretch()
        
        # Create screen container on the right
        screen_container = QWidget()
        screen_layout = QVBoxLayout(screen_container)
        
        # Create stacked widget to hold screens
        self.stacked_widget = QStackedWidget()
        screen_layout.addWidget(self.stacked_widget)
        
        # Create transition manager
        self.transition_manager = ScreenTransitionManager(self.stacked_widget)
        
        # Set initial duration and easing curve
        self.transition_manager.set_duration(400)
        self.transition_manager.set_easing_curve(QEasingCurve.Type.InOutQuad)
        
        # Create screens with different colors
        self.screens = []
        colors = ["#3b4261", "#7aa2f7", "#bb9af7", "#7dcfff", "#ff9e64", "#9ece6a", "#f7768e", "#1a1b26"]
        
        for i, color in enumerate(colors):
            screen = ColorScreen(color)
            screen.set_text(f"Screen {i+1}")
            self.stacked_widget.addWidget(screen)
            self.screens.append(screen)
        
        # Set initial screen
        self.current_screen_index = 0
        self.stacked_widget.setCurrentWidget(self.screens[0])
        
        # Create auto-rotation timer
        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self.next_screen)
        
        # Add controls and screen container to main layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(controls_panel)
        splitter.addWidget(screen_container)
        splitter.setSizes([300, 700])  # Initial sizes
        
        main_layout.addWidget(splitter)
        
        # Apply theming
        stylesheet = load_stylesheet(True)  # Use dark theme
        self.setStyleSheet(stylesheet)
    
    def set_transition_type(self, transition_type):
        """Set the current transition type."""
        self.current_transition = transition_type
        logger.info(f"Set transition type to: {transition_type.name}")
    
    def duration_changed(self, value):
        """Handle duration slider change."""
        self.duration_label.setText(f"{value} ms")
        self.transition_manager.set_duration(value)
    
    def easing_changed(self, index):
        """Handle easing curve change."""
        easing_curve = self.easing_combo.itemData(index)
        self.transition_manager.set_easing_curve(easing_curve)
    
    def trigger_transition(self):
        """Trigger a transition to the next screen."""
        self.next_screen()
    
    def next_screen(self):
        """Switch to the next screen."""
        # Get the next screen index
        next_index = (self.current_screen_index + 1) % len(self.screens)
        self.current_screen_index = next_index
        
        # Get the next screen
        next_screen = self.screens[next_index]
        
        # Perform the transition
        self.transition_manager.transition(next_screen, self.current_transition)
    
    def toggle_auto_rotation(self, checked):
        """Toggle automatic screen rotation."""
        if checked:
            # Start the timer
            interval = self.duration_slider.value() + 1000  # Add 1 second to transition duration
            self.auto_timer.start(interval)
            self.auto_button.setText("Stop Auto Rotation")
        else:
            # Stop the timer
            self.auto_timer.stop()
            self.auto_button.setText("Start Auto Rotation")

def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    
    # Create and show the main window
    window = TransitionTester()
    window.show()
    
    # Start the event loop directly (not in a separate thread)
    return app.exec()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0) 
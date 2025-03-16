#!/usr/bin/env python3
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon

from frontend.style import DARK_COLORS, LIGHT_COLORS, generate_main_stylesheet
from frontend.config import logger

class BaseWindow(QMainWindow):
    """
    Base window class that provides common functionality for all screen types.
    Subclasses should implement the setup_ui_content method to add their specific content.
    """
    # Signals
    theme_changed = pyqtSignal(bool)  # True for dark mode, False for light mode
    window_closed = pyqtSignal()
    window_switch_requested = pyqtSignal(str)  # Emitted when user wants to switch to another window
    
    def __init__(self, title="Smart Display"):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)
        
        # Initialize state
        self.is_dark_mode = True
        self.colors = DARK_COLORS
        self.is_kiosk_mode = False
        
        # Setup UI components
        self.setup_ui()
        
        # Initialize theme
        self.apply_styling()
    
    def setup_ui(self):
        """Setup the base UI components"""
        # Create central widget and main layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        # Create top layout for navigation buttons when in kiosk mode
        self.top_layout = QHBoxLayout()
        self.main_layout.addLayout(self.top_layout)
        
        # Create navigation buttons layout (hidden by default)
        self.nav_layout = QHBoxLayout()
        self.nav_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.top_layout.addWidget(QWidget())  # Placeholder for consistent layout
        self.top_layout.addLayout(self.nav_layout)
        
        # Create content area - to be filled by subclasses
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.content_widget, 1)  # Add with stretch factor
        
        # Call the method that subclasses will implement
        self.setup_ui_content()
        
        # Hide navigation buttons by default (only shown in kiosk mode)
        self.show_navigation_buttons(False)
    
    def setup_ui_content(self):
        """
        To be implemented by subclasses to add their specific content.
        """
        pass
    
    def apply_styling(self):
        """Apply stylesheet to the application"""
        self.setStyleSheet(generate_main_stylesheet(self.colors))
    
    def add_navigation_button(self, window_name, display_name):
        """Add a navigation button for switching to another window"""
        button = QPushButton(display_name)
        button.setFixedHeight(32)
        button.clicked.connect(lambda: self.window_switch_requested.emit(window_name))
        self.nav_layout.addWidget(button)
        return button
    
    def toggle_theme(self):
        """Toggle between light and dark themes"""
        self.is_dark_mode = not self.is_dark_mode
        self.colors = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS
        self.apply_styling()
        self.theme_changed.emit(self.is_dark_mode)
    
    def toggle_kiosk_mode(self):
        """Toggle fullscreen/kiosk mode"""
        self.is_kiosk_mode = not self.is_kiosk_mode
        logger.info(f"{self.__class__.__name__}: Toggling kiosk mode to {self.is_kiosk_mode}")
        
        if self.is_kiosk_mode:
            # Enter kiosk mode
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.showFullScreen()
            # No longer need to show navigation buttons as they're now in the header
            # self.show_navigation_buttons(True)
        else:
            # Exit kiosk mode
            self.setWindowFlags(Qt.WindowType.Window)
            self.showNormal()
            # Hide navigation buttons
            self.show_navigation_buttons(False)
        
        # Update top buttons if they exist
        if hasattr(self, 'top_buttons'):
            logger.info(f"{self.__class__.__name__}: Updating top buttons for kiosk mode {self.is_kiosk_mode}")
            self.top_buttons.set_kiosk_mode(self.is_kiosk_mode)
        else:
            logger.warning(f"{self.__class__.__name__}: No top_buttons attribute found!")
        
        # Need to re-show the window after changing flags
        self.show()
    
    def show_navigation_buttons(self, visible):
        """Show or hide navigation buttons"""
        for i in range(self.nav_layout.count()):
            widget = self.nav_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(visible)
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        # ESC key behavior
        if event.key() == Qt.Key.Key_Escape:
            # If this is the chat window, toggle kiosk mode
            if self.__class__.__name__.lower() == 'chatwindow':
                self.toggle_kiosk_mode()
                
                # If toggling to kiosk mode and we have at least one navigation window available,
                # switch to clock window after a short delay
                if self.is_kiosk_mode and self.nav_layout.count() > 0:
                    QTimer.singleShot(500, lambda: self.window_switch_requested.emit("clock"))
            # For other windows in kiosk mode, return to chat window
            elif self.is_kiosk_mode:
                self.window_switch_requested.emit("chat")
        else:
            super().keyPressEvent(event)
    
    def showEvent(self, event):
        """Handle window show event - ensure proper fullscreen state"""
        # If in kiosk mode, ensure the window is in fullscreen
        if self.is_kiosk_mode:
            logger.info(f"{self.__class__.__name__}: Ensuring fullscreen in kiosk mode")
            self.showFullScreen()
            
        super().showEvent(event)
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info(f"Closing {self.__class__.__name__}")
        self.window_closed.emit()
        super().closeEvent(event) 
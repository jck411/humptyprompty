#!/usr/bin/env python3
import sys
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon

from frontend.config import logger
from frontend.style import DARK_COLORS, LIGHT_COLORS, generate_main_stylesheet

class MainWindow(QMainWindow):
    """
    Main window that hosts all screens in a QStackedWidget.
    This is the persistent single window for the entire application.
    Always runs in fullscreen kiosk mode.
    """
    # Signals
    theme_changed = pyqtSignal(bool, object)  # is_dark_mode, colors
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Display")
        self.setMinimumSize(1024, 768)
        
        # Initialize state
        self.is_dark_mode = True
        self.colors = DARK_COLORS
        
        # Setup UI components
        self.setup_ui()
        
        # Apply initial styling
        self.apply_styling()
        
        # Start in fullscreen kiosk mode immediately
        QTimer.singleShot(100, self.enable_kiosk_mode)
    
    def setup_ui(self):
        """Setup the UI components"""
        # Create central widget and main layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create stacked widget to hold all screens
        self.stacked_widget = QStackedWidget()
        
        # Add stacked widget to main layout
        main_layout.addWidget(self.stacked_widget)
    
    def apply_styling(self):
        """Apply styling to the main window"""
        self.setStyleSheet(generate_main_stylesheet(self.colors))
    
    def toggle_theme(self):
        """Toggle between light and dark theme"""
        logger.info("BEGIN toggle_theme: Toggling theme")
        self.is_dark_mode = not self.is_dark_mode
        self.colors = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS
        theme_name = "Dark" if self.is_dark_mode else "Light"
        logger.info(f"Switching to {theme_name} theme")
        
        # Apply styling to the main window
        self.apply_styling()
        
        # Emit signal for screens to update their theme
        logger.info(f"Emitting theme_changed signal with is_dark_mode={self.is_dark_mode}")
        self.theme_changed.emit(self.is_dark_mode, self.colors)
        logger.info("END toggle_theme: Theme toggle complete")
    
    def add_screen(self, screen, name):
        """
        Add a screen to the stacked widget
        
        Args:
            screen: The screen widget to add
            name: A unique name for the screen
        
        Returns:
            The index of the added screen
        """
        return self.stacked_widget.addWidget(screen)
    
    def show_screen(self, index_or_name):
        """
        Show the screen at the given index or with the given name
        
        Args:
            index_or_name: Either the index or name of the screen to show
        """
        if isinstance(index_or_name, int):
            self.stacked_widget.setCurrentIndex(index_or_name)
        else:
            # Find the widget with the given name
            for i in range(self.stacked_widget.count()):
                if self.stacked_widget.widget(i).objectName() == index_or_name:
                    self.stacked_widget.setCurrentIndex(i)
                    break
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        # No need to handle ESC or F11 keys anymore as we're always in kiosk mode
        super().keyPressEvent(event)
    
    def enable_kiosk_mode(self):
        """Enable fullscreen kiosk mode"""
        # Enable fullscreen
        self.showFullScreen()
        # Hide window frame
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        # Show the window after changing flags
        self.show()
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Closing application...")
        # Propagate close event to all screens
        for i in range(self.stacked_widget.count()):
            widget = self.stacked_widget.widget(i)
            if hasattr(widget, 'cleanup'):
                widget.cleanup()
        super().closeEvent(event) 
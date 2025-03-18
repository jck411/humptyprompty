#!/usr/bin/env python3
from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPixmap, QImage

from frontend.base_screen import BaseScreen

class PhotosScreen(BaseScreen):
    """
    Screen that displays a slideshow of photos.
    This is a placeholder implementation that would be connected to a photo source.
    """
    def __init__(self, colors):
        super().__init__(colors)
        
        # Initialize state
        self.current_photo_index = 0
        self.photo_paths = [
            # Placeholder photo paths - in a real implementation, these would be loaded from a directory
            "frontend/icons/photos.svg",  # Using the photos icon as a placeholder
        ]
        
        # Setup UI components
        self.setup_ui()
        
        # Create timer for slideshow
        self.slideshow_timer = QTimer(self)
        self.slideshow_timer.timeout.connect(self.next_photo)
        
    def setup_ui(self):
        """Setup the UI components"""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create photo label
        self.photo_label = QLabel()
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setMinimumSize(400, 300)
        self.photo_label.setStyleSheet("background-color: rgba(0, 0, 0, 0.1); border-radius: 10px;")
        
        # Add label to layout
        main_layout.addWidget(self.photo_label)
        
        # Apply initial styling
        self.update_colors(self.colors)
        
    def load_photo(self, path):
        """Load a photo from the given path and display it"""
        # In a real implementation, this would handle different image formats and sizes
        pixmap = QPixmap(path)
        
        if not pixmap.isNull():
            # Scale the pixmap to fit the label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.photo_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.photo_label.setPixmap(scaled_pixmap)
        else:
            # If the pixmap is null, display a placeholder
            self.photo_label.setText("No photo available")
        
    def next_photo(self):
        """Display the next photo in the slideshow"""
        if not self.photo_paths:
            return
            
        self.current_photo_index = (self.current_photo_index + 1) % len(self.photo_paths)
        self.load_photo(self.photo_paths[self.current_photo_index])
        
    def activate(self):
        """Called when the screen becomes active"""
        # Load the first photo
        if self.photo_paths:
            self.load_photo(self.photo_paths[self.current_photo_index])
            
        # Start the slideshow timer
        self.slideshow_timer.start(5000)  # Change photo every 5 seconds
        
    def deactivate(self):
        """Called when the screen is about to be hidden"""
        # Stop the slideshow timer
        self.slideshow_timer.stop()
        
    def update_colors(self, colors):
        """Update the color scheme"""
        super().update_colors(colors)
        
        # Update photo label background color
        background_color = colors['input_background'] if 'input_background' in colors else colors['background']
        self.photo_label.setStyleSheet(f"background-color: {background_color}; border-radius: 10px;")
        
    def resizeEvent(self, event):
        """Handle resize events to scale the current photo"""
        super().resizeEvent(event)
        
        # Reload the current photo to scale it properly
        if self.photo_paths:
            self.load_photo(self.photo_paths[self.current_photo_index])

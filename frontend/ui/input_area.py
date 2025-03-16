#!/usr/bin/env python3
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QColor, QPalette

from frontend.ui.text_input import CustomTextEdit

class InputArea(QWidget):
    """
    UI component for the input area at the bottom of the chat window.
    """
    # Signals
    send_clicked = pyqtSignal()
    text_changed = pyqtSignal()
    
    def __init__(self, colors):
        super().__init__()
        self.colors = colors
        
        # Setup layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 5, 10, 10)
        self.main_layout.setSpacing(5)
        
        # Create text input
        self.text_input = CustomTextEdit(self)
        self.text_input.textChanged.connect(self.on_text_changed)
        
        # Set placeholder text color
        palette = self.text_input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(self.colors['text_secondary']))
        self.text_input.setPalette(palette)
        
        # Create button widget
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(5, 0, 0, 0)
        button_layout.setSpacing(5)
        
        # Create send button
        self.send_button = QPushButton()
        self.send_button.setFixedSize(50, 50)
        self.send_button.setIcon(QIcon("frontend/icons/send.svg"))
        self.send_button.setIconSize(QSize(24, 24))
        self.send_button.clicked.connect(self.on_send_clicked)
        
        # Add buttons to layout
        button_layout.addWidget(self.send_button)
        
        # Add widgets to main layout
        self.main_layout.addWidget(self.text_input, stretch=1)
        self.main_layout.addWidget(button_widget)
    
    def on_send_clicked(self):
        """Handle send button click"""
        self.send_clicked.emit()
    
    def on_text_changed(self):
        """Handle text input changes"""
        self.adjust_text_input_height()
        self.text_changed.emit()
    
    def adjust_text_input_height(self):
        """Adjust the height of the text input based on content"""
        doc_height = self.text_input.document().size().height()
        new_height = min(max(50, doc_height + 20), 100)
        self.text_input.setFixedHeight(int(new_height))
    
    def get_text(self):
        """Get the current text from the input field"""
        return self.text_input.toPlainText()
    
    def clear_text(self):
        """Clear the text input field"""
        self.text_input.clear()
    
    def set_text(self, text):
        """Set the text in the input field"""
        self.text_input.setPlainText(text)
        # Place cursor at the end of the text
        cursor = self.text_input.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.text_input.setTextCursor(cursor)
        # Adjust height after setting text
        self.adjust_text_input_height()
    
    def update_colors(self, colors):
        """Update the color scheme"""
        self.colors = colors
        
        # Update placeholder text color
        palette = self.text_input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(self.colors['text_secondary']))
        self.text_input.setPalette(palette) 
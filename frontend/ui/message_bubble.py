#!/usr/bin/env python3
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel

class MessageBubble(QFrame):
    """
    UI component that displays a message bubble in the chat area.
    """
    def __init__(self, text, is_user=True):
        super().__init__()
        self.setObjectName("messageBubble")
        # Set property for CSS selector - using string "true"/"false" for Qt stylesheet compatibility
        self.setProperty("isUser", "true" if is_user else "false")
        
        # Setup layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create label for message text
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("font-size: 14px;")
        
        # Add label to layout
        layout.addWidget(self.label)

    def update_text(self, new_text):
        """Update the text displayed in the message bubble"""
        self.label.setText(new_text) 
#!/usr/bin/env python3
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QSizePolicy
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

from frontend.ui.message_bubble import MessageBubble
from frontend.style import get_message_bubble_stylesheet

class ChatArea(QWidget):
    """
    UI component that displays the chat messages.
    """
    def __init__(self, colors):
        super().__init__()
        self.colors = colors
        self.assistant_bubble_in_progress = None
        
        # Setup main widget
        self.chat_widget = QWidget()
        self.chat_widget.setAutoFillBackground(True)
        self.chat_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Set background color
        chat_palette = self.chat_widget.palette()
        chat_palette.setColor(QPalette.ColorRole.Window, QColor(self.colors['background']))
        self.chat_widget.setPalette(chat_palette)
        
        # Setup layout
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(2)
        self.chat_layout.addStretch()
        
        # Setup scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setWidget(self.chat_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setAutoFillBackground(True)
        
        # Set scroll area background color
        scroll_palette = self.scroll_area.palette()
        scroll_palette.setColor(QPalette.ColorRole.Window, QColor(self.colors['background']))
        self.scroll_area.setPalette(scroll_palette)
        
        # Setup main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.scroll_area)
    
    def add_message(self, text, is_user):
        """Add a new message bubble to the chat area"""
        bubble = MessageBubble(text, is_user)
        bubble.setStyleSheet(get_message_bubble_stylesheet(is_user, self.colors))
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self.auto_scroll()
        return bubble
    
    def update_assistant_message(self, token):
        """Update the current assistant message with a new token"""
        if not self.assistant_bubble_in_progress:
            self.assistant_bubble_in_progress = self.add_message("", is_user=False)
        
        current_text = self.assistant_bubble_in_progress.label.text()
        self.assistant_bubble_in_progress.update_text(current_text + token)
        self.auto_scroll()
    
    def finalize_assistant_message(self):
        """Finalize the current assistant message"""
        self.assistant_bubble_in_progress = None
    
    def auto_scroll(self):
        """Automatically scroll to the bottom of the chat area"""
        vsb = self.scroll_area.verticalScrollBar()
        vsb.setValue(vsb.maximum())
    
    def clear(self):
        """Clear all messages from the chat area"""
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.chat_layout.addStretch()
        self.assistant_bubble_in_progress = None
    
    def update_colors(self, colors):
        """Update the color scheme"""
        self.colors = colors
        
        # Update chat widget background
        chat_palette = self.chat_widget.palette()
        chat_palette.setColor(QPalette.ColorRole.Window, QColor(self.colors['background']))
        self.chat_widget.setPalette(chat_palette)
        
        # Update scroll area background
        scroll_palette = self.scroll_area.palette()
        scroll_palette.setColor(QPalette.ColorRole.Window, QColor(self.colors['background']))
        self.scroll_area.setPalette(scroll_palette)
        
        # Update message bubbles
        for i in range(self.chat_layout.count()):
            item = self.chat_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), MessageBubble):
                widget = item.widget()
                is_user = widget.property("isUser")
                widget.setStyleSheet(get_message_bubble_stylesheet(is_user, self.colors)) 
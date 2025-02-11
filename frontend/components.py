from PyQt6.QtWidgets import (
    QFrame, QLabel, QTextEdit, QVBoxLayout
)
from PyQt6.QtCore import Qt
from config import COLORS

class MessageBubble(QFrame):
    def __init__(self, text, is_user=True, parent=None):
        super().__init__(parent)
        self.setObjectName("messageBubble")
        self.setProperty("isUser", is_user)
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)
        
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setOpenExternalLinks(True)
        
        if is_user:
            self.setStyleSheet(f"""
                QFrame#messageBubble {{
                    background-color: {COLORS['user_bubble']};
                    border-radius: 15px;
                    margin: 5px 50px 5px 5px;
                    padding: 5px;
                }}
                QLabel {{
                    color: {COLORS['text_primary']};
                    font-size: 14px;
                    background-color: transparent;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#messageBubble {{
                    background-color: transparent;
                    margin: 5px 5px 5px 50px;
                    padding: 5px;
                }}
                QLabel {{
                    color: {COLORS['text_primary']};
                    font-size: 14px;
                    background-color: transparent;
                }}
            """)
        
        layout.addWidget(self.label)

    def update_text(self, new_text):
        self.label.setText(new_text)

class CustomTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def keyPressEvent(self, event):
        if (event.key() == Qt.Key.Key_Return and 
            not event.modifiers() & Qt.KeyboardModifier.ShiftModifier and 
            self.parent is not None):
            self.parent.send_message()
        else:
            super().keyPressEvent(event)
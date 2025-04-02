# user_icon.py
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QBrush, QColor, QFont
from PyQt6.QtCore import Qt

class UserIcon(QWidget):
    def __init__(self, username, size=40):
        super().__init__()
        self.username = username[0].upper()
        self.size = size
        self.setFixedSize(self.size, self.size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("lightblue")))
        painter.drawEllipse(0, 0, self.size, self.size)
        painter.setPen(QColor("black"))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.username)

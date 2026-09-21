"""편집 씬 — 격자 배경과 페이지 경계."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsScene


class DiagramScene(QGraphicsScene):
    def __init__(self, grid_step: int = 10, parent=None):
        super().__init__(parent)
        self.grid_step = grid_step
        self.show_grid = True
        self.setBackgroundBrush(QColor(255, 255, 255))
        self.setSceneRect(QRectF(-2000, -2000, 4000, 4000))

    def drawBackground(self, painter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor(255, 255, 255))
        if not self.show_grid:
            return
        step = self.grid_step
        left = int(rect.left()) - (int(rect.left()) % step)
        top = int(rect.top()) - (int(rect.top()) % step)

        minor = QPen(QColor(232, 236, 242))
        minor.setWidth(0)
        major = QPen(QColor(210, 216, 226))
        major.setWidth(0)

        x = left
        while x < rect.right():
            painter.setPen(major if (x % (step * 5) == 0) else minor)
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += step
        y = top
        while y < rect.bottom():
            painter.setPen(major if (y % (step * 5) == 0) else minor)
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += step

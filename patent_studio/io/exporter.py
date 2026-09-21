"""내보내기 — 격자/선택핸들 없는 깨끗한 흑백 도면을 PNG/SVG 로.

편집 씬과 분리된 임시 씬에서 렌더링해 UI 잔여물이 섞이지 않게 한다.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, QMarginsF, Qt
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QGraphicsScene

from ..core import model as M
from ..diagram.items import ShapeItem


class _NullCtl:
    """내보내기용 무동작 컨트롤러."""
    snap_enabled = False
    grid_step = 10

    def begin_interaction(self): ...
    def commit_interaction(self, label): ...
    def notify_geometry_changed(self, item): ...
    def notify_text_edited(self, item): ...


def _build_scene(doc: M.Document) -> QGraphicsScene:
    scene = QGraphicsScene()
    scene.setBackgroundBrush(QColor(255, 255, 255))
    ctl = _NullCtl()
    for el in sorted(doc.elements, key=lambda e: e.z):
        if el.type == M.TYPE_SHAPE:
            scene.addItem(ShapeItem(el, ctl))
    return scene


def _content_rect(scene: QGraphicsScene, pad: float = 24.0) -> QRectF:
    r = scene.itemsBoundingRect()
    if r.isNull():
        r = QRectF(0, 0, 100, 100)
    return r.marginsAdded(QMarginsF(pad, pad, pad, pad))


def export_png(doc: M.Document, path: str, scale: float = 3.0) -> None:
    scene = _build_scene(doc)
    rect = _content_rect(scene)
    img = QImage(int(rect.width() * scale), int(rect.height() * scale),
                 QImage.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    scene.render(p, QRectF(img.rect()), rect)
    p.end()
    img.save(path, "PNG")


def export_svg(doc: M.Document, path: str) -> None:
    scene = _build_scene(doc)
    rect = _content_rect(scene)
    gen = QSvgGenerator()
    gen.setFileName(path)
    gen.setSize(rect.size().toSize())
    gen.setViewBox(QRectF(0, 0, rect.width(), rect.height()))
    gen.setTitle("Patent Block Diagram")
    p = QPainter(gen)
    p.setRenderHint(QPainter.Antialiasing, True)
    scene.render(p, QRectF(0, 0, rect.width(), rect.height()), rect)
    p.end()

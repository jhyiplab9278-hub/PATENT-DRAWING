"""편집 가능한 도형 아이템 — 이동/8핸들 리사이즈/회전/인라인 텍스트.

컨트롤러(편집 위젯)는 다음을 제공한다고 가정한다:
  begin_interaction(), commit_interaction(label),
  snap_enabled(bool 속성), grid_step(float 속성),
  notify_geometry_changed(item), notify_text_edited(item)
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
                           QTextOption)
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsObject,
                               QGraphicsTextItem, QStyle)

from ..core import model as M
from ..core import geometry as G
from . import shapes

BLACK = QColor(0, 0, 0)
HANDLE_FILL = QColor(255, 255, 255)
HANDLE_LINE = QColor(30, 90, 220)
ROT_LINE = QColor(230, 140, 20)


def _pen_for(style: M.Style, scale: float = 1.0) -> QPen:
    pen = QPen(BLACK)
    pen.setWidthF(max(0.4, style.line))
    pen.setJoinStyle(Qt.MiterJoin)
    pen.setCapStyle(Qt.FlatCap)
    if style.dash == M.DASH_DASHED:
        pen.setStyle(Qt.CustomDashLine)
        pen.setDashPattern([4, 3])
    elif style.dash == M.DASH_DASHDOT:
        pen.setStyle(Qt.CustomDashLine)
        pen.setDashPattern([6, 3, 1, 3])
    else:
        pen.setStyle(Qt.SolidLine)
    return pen


class _EditableText(QGraphicsTextItem):
    """더블클릭 인라인 편집용 텍스트. 부모 도형에 커밋을 알린다."""

    def __init__(self, parent: "ShapeItem"):
        super().__init__(parent)
        self._owner = parent
        self.setDefaultTextColor(BLACK)
        f = QFont("Malgun Gothic")
        f.setPointSizeF(11)
        self.setFont(f)
        opt = QTextOption()
        opt.setAlignment(Qt.AlignCenter)
        opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(opt)
        self.setTextInteractionFlags(Qt.NoTextInteraction)

    def focusOutEvent(self, ev):
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        cur = self.textCursor()
        cur.clearSelection()
        self.setTextCursor(cur)
        self._owner._finish_text_edit()
        super().focusOutEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.clearFocus()
            return
        # Ctrl+Enter 또는 Enter(수정자 없음)로 편집 종료, Shift+Enter 는 줄바꿈
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and not (ev.modifiers() & Qt.ShiftModifier):
            self.clearFocus()
            return
        super().keyPressEvent(ev)


class ShapeItem(QGraphicsObject):
    def __init__(self, element: M.Element, controller):
        super().__init__()
        self.el = element
        self.ctl = controller
        self._mode: Optional[str] = None      # None|'move'|'resize'|'rotate'
        self._resize_key: Optional[str] = None
        self._suppress_snap = False
        self._moved = False

        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        self.text = _EditableText(self)
        self.apply_from_element()

    # ------------------------------------------------------------------ 동기화
    def apply_from_element(self) -> None:
        el = self.el
        self.prepareGeometryChange()
        self.setTransformOriginPoint(el.w / 2, el.h / 2)
        self._suppress_snap = True
        self.setPos(el.x, el.y)
        self._suppress_snap = False
        self.setRotation(el.rotation)
        self.setZValue(el.z)
        self._layout_text()
        self.update()

    def _layout_text(self) -> None:
        self.text.setPlainText(self.el.text)
        self.text.setTextWidth(self.el.w)
        tb = self.text.boundingRect()
        self.text.setPos(0, max(0, (self.el.h - tb.height()) / 2))

    # --------------------------------------------------------------- 표시 영역
    def _vs(self) -> float:
        sc = self.scene()
        if sc and sc.views():
            m = sc.views()[0].transform().m11()
            return m if m else 1.0
        return 1.0

    def boundingRect(self) -> QRectF:
        m = 12 / self._vs()
        rot = 26 / self._vs()
        return QRectF(-m, -rot, self.el.w + 2 * m, self.el.h + rot + m)

    def shape(self) -> QPainterPath:
        p = shapes.path_for(self.el.shape, self.el.w, self.el.h)
        # 채움 없는 도형도 내부 클릭으로 선택되도록 사각 영역 포함
        p.addRect(0, 0, self.el.w, self.el.h)
        if self.isSelected():
            for _, pt in self._handle_points().items():
                r = 8 / self._vs()
                p.addRect(pt.x() - r, pt.y() - r, 2 * r, 2 * r)
        return p

    # -------------------------------------------------------------------- 그리기
    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing, True)
        body = shapes.path_for(self.el.shape, self.el.w, self.el.h)
        if self.el.style.fill == M.FILL_WHITE:
            painter.fillPath(body, QBrush(QColor(255, 255, 255)))
        painter.setPen(_pen_for(self.el.style))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(body)

        if self.isSelected():
            self._paint_handles(painter)

    def _paint_handles(self, painter: QPainter) -> None:
        vs = self._vs()
        hs = 7 / vs
        pen = QPen(HANDLE_LINE)
        pen.setWidthF(1.2 / vs)
        painter.setPen(pen)
        # 선택 외곽 점선
        outline = QPen(HANDLE_LINE)
        outline.setWidthF(1.0 / vs)
        outline.setStyle(Qt.DashLine)
        painter.setPen(outline)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, self.el.w, self.el.h)

        pts = self._handle_points()
        painter.setPen(pen)
        painter.setBrush(QBrush(HANDLE_FILL))
        for key, pt in pts.items():
            if key == "rotate":
                continue
            painter.drawRect(QRectF(pt.x() - hs, pt.y() - hs, 2 * hs, 2 * hs))
        # 회전 손잡이
        rp = pts["rotate"]
        rpen = QPen(ROT_LINE)
        rpen.setWidthF(1.2 / vs)
        painter.setPen(rpen)
        painter.drawLine(QPointF(self.el.w / 2, 0), rp)
        painter.setBrush(QBrush(HANDLE_FILL))
        painter.drawEllipse(rp, hs, hs)

    def _handle_points(self) -> dict[str, QPointF]:
        w, h = self.el.w, self.el.h
        rot = 24 / self._vs()
        return {
            "nw": QPointF(0, 0), "n": QPointF(w / 2, 0), "ne": QPointF(w, 0),
            "e": QPointF(w, h / 2), "se": QPointF(w, h), "s": QPointF(w / 2, h),
            "sw": QPointF(0, h), "w": QPointF(0, h / 2),
            "rotate": QPointF(w / 2, -rot),
        }

    def _handle_at(self, pos: QPointF) -> Optional[str]:
        r = 8 / self._vs()
        for key, pt in self._handle_points().items():
            if abs(pos.x() - pt.x()) <= r and abs(pos.y() - pt.y()) <= r:
                return key
        return None

    # -------------------------------------------------------------------- 입력
    def mouseDoubleClickEvent(self, ev):
        self.text.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.text.setFocus(Qt.MouseFocusReason)
        cur = self.text.textCursor()
        cur.select(cur.SelectionType.Document)
        self.text.setTextCursor(cur)
        ev.accept()

    def _finish_text_edit(self) -> None:
        new_text = self.text.toPlainText()
        if new_text != self.el.text:
            self.ctl.begin_interaction()
            self.el.text = new_text
            self._layout_text()
            self.ctl.commit_interaction("텍스트 편집")
        else:
            self._layout_text()

    def mousePressEvent(self, ev):
        if self.isSelected() and ev.button() == Qt.LeftButton:
            key = self._handle_at(ev.pos())
            if key == "rotate":
                self._mode = "rotate"
                self.ctl.begin_interaction()
                ev.accept()
                return
            if key is not None:
                self._mode = "resize"
                self._resize_key = key
                self.ctl.begin_interaction()
                ev.accept()
                return
        self._mode = "move"
        self._moved = False
        self.ctl.begin_interaction()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._mode == "resize":
            keep = bool(ev.modifiers() & Qt.ShiftModifier)
            m = ev.scenePos()
            nx, ny, nw, nh = G.resize(
                self._resize_key,
                self.pos().x(), self.pos().y(), self.el.w, self.el.h,
                self.rotation(), G.Pt(m.x(), m.y()), keep_ratio=keep,
            )
            self.prepareGeometryChange()
            self.el.w, self.el.h = nw, nh
            self.setTransformOriginPoint(nw / 2, nh / 2)
            self._suppress_snap = True
            self.setPos(nx, ny)
            self._suppress_snap = False
            self._layout_text()
            self.update()
            self.ctl.notify_geometry_changed(self)
            ev.accept()
            return
        if self._mode == "rotate":
            c = self.mapToScene(self.el.w / 2, self.el.h / 2)
            m = ev.scenePos()
            snap = bool(ev.modifiers() & Qt.ShiftModifier)
            ang = G.rotation_from_mouse(c.x(), c.y(), G.Pt(m.x(), m.y()), snap=snap)
            self.el.rotation = ang
            self.setRotation(ang)
            self.ctl.notify_geometry_changed(self)
            ev.accept()
            return
        self._moved = True
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        mode = self._mode
        self._mode = None
        self._resize_key = None
        if mode == "resize":
            self._apply_grid_snap_size()
            self.ctl.commit_interaction("크기 조절")
        elif mode == "rotate":
            self.ctl.commit_interaction("회전")
        else:
            super().mouseReleaseEvent(ev)
            if self._moved:
                self.ctl.commit_interaction("이동")

    def _apply_grid_snap_size(self) -> None:
        if not getattr(self.ctl, "snap_enabled", False):
            return
        step = getattr(self.ctl, "grid_step", 10)
        self.el.w = max(G.MIN_SIZE, G.snap_to_grid(self.el.w, step))
        self.el.h = max(G.MIN_SIZE, G.snap_to_grid(self.el.h, step))
        self.apply_from_element()

    # -------------------------------------------------------------- itemChange
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and not self._suppress_snap:
            if getattr(self.ctl, "snap_enabled", False) and self._mode == "move":
                step = getattr(self.ctl, "grid_step", 10)
                value = QPointF(G.snap_to_grid(value.x(), step),
                                G.snap_to_grid(value.y(), step))
            return value
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.el.x = self.pos().x()
            self.el.y = self.pos().y()
            self.ctl.notify_geometry_changed(self)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.update()
        return super().itemChange(change, value)

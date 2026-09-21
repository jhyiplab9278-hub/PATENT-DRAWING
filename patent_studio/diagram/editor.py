"""블록도 편집 위젯 — 문서 보유, Undo 관리, 아이템 컨트롤러.

통합 시 이 위젯(DiagramEditorWidget)만 최종 앱에 임베드하면 된다.
Undo 는 스냅샷(문서 JSON) 방식: 단순하고 견고하며 MVP 규모에 충분하다.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QUndoCommand, QUndoStack
from PySide6.QtWidgets import QGraphicsView

from ..core import model as M
from ..core import geometry as G
from .scene import DiagramScene
from .items import ShapeItem


class _Snapshot(QUndoCommand):
    def __init__(self, editor: "DiagramEditorWidget", before: str, after: str, text: str):
        super().__init__(text)
        self.ed = editor
        self.before = before
        self.after = after
        self._first = True

    def redo(self):
        # push 직후의 첫 redo 는 이미 after 상태이므로 재구성 생략(선택 유지)
        if self._first:
            self._first = False
            return
        self.ed._load_snapshot(self.after)

    def undo(self):
        self.ed._load_snapshot(self.before)


class DiagramEditorWidget(QGraphicsView):
    selection_changed = Signal()
    document_changed = Signal()

    def __init__(self, doc: Optional[M.Document] = None, parent=None):
        super().__init__(parent)
        self.doc = doc or M.Document()
        self.grid_step = 10
        self.snap_enabled = True

        self._scene = DiagramScene(self.grid_step)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        self.undo_stack = QUndoStack(self)
        self._pending_before: Optional[str] = None
        self._loading = False

        self._scene.selectionChanged.connect(self.selection_changed.emit)
        self._rebuild_items()

    # ---------------------------------------------------------------- 컨트롤러 API
    def begin_interaction(self) -> None:
        if self._loading:
            return
        if self._pending_before is None:
            self._pending_before = self.doc.to_json(indent=0)

    def commit_interaction(self, label: str) -> None:
        if self._loading or self._pending_before is None:
            return
        after = self.doc.to_json(indent=0)
        if after != self._pending_before:
            self.undo_stack.push(_Snapshot(self, self._pending_before, after, label))
            self.document_changed.emit()
        self._pending_before = None

    def notify_geometry_changed(self, item) -> None:
        pass  # 연결선/태그 추적은 후속 단계

    def notify_text_edited(self, item) -> None:
        pass

    # ---------------------------------------------------------------- 스냅샷 재구성
    def _load_snapshot(self, snap: str) -> None:
        self._loading = True
        self.doc = M.Document.from_json(snap)
        self._rebuild_items()
        self._loading = False
        self.document_changed.emit()
        self.selection_changed.emit()

    def _rebuild_items(self) -> None:
        self._scene.clear()
        self._scene.grid_step = self.grid_step
        for el in sorted(self.doc.elements, key=lambda e: e.z):
            if el.type == M.TYPE_SHAPE:
                self._scene.addItem(ShapeItem(el, self))

    def selected_items(self) -> list[ShapeItem]:
        return [it for it in self._scene.selectedItems() if isinstance(it, ShapeItem)]

    # ---------------------------------------------------------------- 편집 명령
    def add_shape(self, shape: str, x: float = 60, y: float = 60,
                  w: float = 160, h: float = 80) -> ShapeItem:
        self.begin_interaction()
        el = M.Element(id=self.doc.new_id(), type=M.TYPE_SHAPE, shape=shape,
                       x=x, y=y, w=w, h=h, z=self.doc.max_z() + 1)
        if shape == M.SHAPE_USER:
            el.w, el.h = 90, 100
        self.doc.add(el)
        item = ShapeItem(el, self)
        self._scene.addItem(item)
        self._scene.clearSelection()
        item.setSelected(True)
        self.commit_interaction("도형 추가")
        return item

    def delete_selected(self) -> None:
        items = self.selected_items()
        if not items:
            return
        self.begin_interaction()
        for it in items:
            self.doc.remove(it.el.id)
            self._scene.removeItem(it)
        self.commit_interaction("삭제")

    def cycle_dash_selected(self) -> None:
        items = self.selected_items()
        if not items:
            return
        self.begin_interaction()
        for it in items:
            cur = it.el.style.dash
            nxt = M.DASH_CYCLE[(M.DASH_CYCLE.index(cur) + 1) % len(M.DASH_CYCLE)]
            it.el.style.dash = nxt
            it.update()
        self.commit_interaction("선종 변경")

    def change_line_width_selected(self, delta: float) -> None:
        items = self.selected_items()
        if not items:
            return
        self.begin_interaction()
        for it in items:
            it.el.style.line = max(0.4, round(it.el.style.line + delta, 1))
            it.update()
        self.commit_interaction("선 굵기")

    def toggle_fill_selected(self) -> None:
        items = self.selected_items()
        if not items:
            return
        self.begin_interaction()
        for it in items:
            it.el.style.fill = (M.FILL_WHITE if it.el.style.fill == M.FILL_NONE
                                else M.FILL_NONE)
            it.update()
        self.commit_interaction("채움")

    def _reorder(self, to_front: bool) -> None:
        items = self.selected_items()
        if not items:
            return
        self.begin_interaction()
        base = self.doc.max_z() + 1 if to_front else min(
            (e.z for e in self.doc.elements), default=0) - len(items)
        for i, it in enumerate(items):
            it.el.z = base + i
            it.setZValue(it.el.z)
        self.commit_interaction("순서 변경")

    def bring_to_front(self) -> None:
        self._reorder(True)

    def send_to_back(self) -> None:
        self._reorder(False)

    # ---------------------------------------------------------------- 뷰 조작
    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            factor = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            ev.accept()
        else:
            super().wheelEvent(ev)

    @staticmethod
    def _is_text_editing(item) -> bool:
        try:
            return bool(item.textInteractionFlags() & Qt.TextEditorInteraction)
        except AttributeError:
            return False

    def keyPressEvent(self, ev):
        # 인라인 텍스트 편집 중이면 도형 단축키를 가로채지 않는다
        fi = self._scene.focusItem()
        if fi is not None and self._is_text_editing(fi):
            super().keyPressEvent(ev)
            return
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
            ev.accept()
            return
        step = self.grid_step if (ev.modifiers() & Qt.ShiftModifier) else 1
        dx = dy = 0
        if ev.key() == Qt.Key_Left:
            dx = -step
        elif ev.key() == Qt.Key_Right:
            dx = step
        elif ev.key() == Qt.Key_Up:
            dy = -step
        elif ev.key() == Qt.Key_Down:
            dy = step
        if dx or dy:
            items = self.selected_items()
            if items:
                self.begin_interaction()
                for it in items:
                    it.el.x += dx
                    it.el.y += dy
                    it.apply_from_element()
                self.commit_interaction("이동")
                ev.accept()
                return
        super().keyPressEvent(ev)

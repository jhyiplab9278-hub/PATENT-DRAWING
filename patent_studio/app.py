"""독립 실행 진입점 — 최종 통합 앱과 분리된 얇은 껍데기.

편집 엔진(DiagramEditorWidget)은 그대로 통합 앱에 임베드된다.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QMainWindow,
                               QMessageBox, QToolBar, QWidget)

from .core import model as M
from .diagram.editor import DiagramEditorWidget
from .io import exporter, pbd_import

PROJECT_EXT = "pdblk"   # 우리 프로젝트 확장자 (블록도)
PROJECT_FILTER = f"블록도 프로젝트 (*.{PROJECT_EXT})"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("특허 블록도 에디터 (우리식) — v0.1")
        self.resize(1200, 800)

        self.editor = DiagramEditorWidget()
        self.setCentralWidget(self.editor)
        self.path: Path | None = None

        self._build_toolbar()
        self._build_menu()
        self.editor.document_changed.connect(self._update_title)
        self._update_title()

    # ---------------------------------------------------------------- UI 구성
    def _build_toolbar(self) -> None:
        tb = QToolBar("도구")
        tb.setMovable(False)
        self.addToolBar(tb)

        def add(label, slot, tip=""):
            a = QAction(label, self)
            a.triggered.connect(slot)
            if tip:
                a.setToolTip(tip)
            tb.addAction(a)
            return a

        add("□ 사각", lambda: self.editor.add_shape(M.SHAPE_RECT))
        add("▢ 둥근", lambda: self.editor.add_shape(M.SHAPE_ROUNDED))
        add("⛁ DB", lambda: self.editor.add_shape(M.SHAPE_CYLINDER, w=140, h=110))
        add("☁ 망", lambda: self.editor.add_shape(M.SHAPE_CLOUD, w=180, h=120))
        add("👤 사용자", lambda: self.editor.add_shape(M.SHAPE_USER))
        tb.addSeparator()
        add("선종", self.editor.cycle_dash_selected, "실선→점선→일점쇄선")
        add("선 +", lambda: self.editor.change_line_width_selected(0.5))
        add("선 −", lambda: self.editor.change_line_width_selected(-0.5))
        add("채움", self.editor.toggle_fill_selected, "없음 ↔ 흰색")
        tb.addSeparator()
        add("맨앞", self.editor.bring_to_front)
        add("맨뒤", self.editor.send_to_back)
        add("삭제", self.editor.delete_selected)
        tb.addSeparator()
        self.act_snap = QAction("스냅", self, checkable=True)
        self.act_snap.setChecked(True)
        self.act_snap.toggled.connect(self._toggle_snap)
        tb.addAction(self.act_snap)
        add("맞춤", self._fit)

    def _build_menu(self) -> None:
        mb = self.menuBar()
        m_file = mb.addMenu("파일")

        def mk(menu, label, slot, shortcut=None):
            a = QAction(label, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            menu.addAction(a)
            return a

        mk(m_file, "새로 만들기", self._new, "Ctrl+N")
        mk(m_file, "열기…", self._open, "Ctrl+O")
        mk(m_file, "저장", self._save, "Ctrl+S")
        mk(m_file, "다른 이름으로 저장…", self._save_as, "Ctrl+Shift+S")
        m_file.addSeparator()
        mk(m_file, "레거시 .pbd 가져오기…", self._import_pbd)
        m_file.addSeparator()
        mk(m_file, "PNG 내보내기…", self._export_png)
        mk(m_file, "SVG 내보내기…", self._export_svg)

        m_edit = mb.addMenu("편집")
        undo = self.editor.undo_stack.createUndoAction(self, "실행 취소")
        undo.setShortcut(QKeySequence.Undo)
        redo = self.editor.undo_stack.createRedoAction(self, "다시 실행")
        redo.setShortcut(QKeySequence("Ctrl+Y"))
        m_edit.addAction(undo)
        m_edit.addAction(redo)

    # ---------------------------------------------------------------- 동작
    def _toggle_snap(self, on: bool) -> None:
        self.editor.snap_enabled = on

    def _fit(self) -> None:
        r = self.editor._scene.itemsBoundingRect()
        if not r.isNull():
            self.editor.fitInView(r.adjusted(-40, -40, 40, 40), Qt.KeepAspectRatio)

    def _update_title(self) -> None:
        name = self.path.name if self.path else "제목 없음"
        self.setWindowTitle(f"특허 블록도 에디터 (우리식) — {name}")

    def _new(self) -> None:
        self.editor.doc = M.Document()
        self.editor.undo_stack.clear()
        self.editor._rebuild_items()
        self.path = None
        self._update_title()

    def _open(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "열기", "", PROJECT_FILTER)
        if not fn:
            return
        try:
            doc = M.Document.from_json(Path(fn).read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "열기 실패", str(e))
            return
        self.editor.doc = doc
        self.editor.undo_stack.clear()
        self.editor._rebuild_items()
        self.path = Path(fn)
        self._update_title()

    def _save(self) -> None:
        if self.path is None:
            self._save_as()
            return
        self.path.write_text(self.editor.doc.to_json(), encoding="utf-8")

    def _save_as(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(self, "저장", f"도면.{PROJECT_EXT}", PROJECT_FILTER)
        if not fn:
            return
        self.path = Path(fn)
        self._save()
        self._update_title()

    def _import_pbd(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "레거시 가져오기", "", "레거시 (*.pbd)")
        if not fn:
            return
        try:
            doc = pbd_import.import_pbd(Path(fn).read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "가져오기 실패", str(e))
            return
        self.editor.doc = doc
        self.editor.undo_stack.clear()
        self.editor._rebuild_items()
        self.path = None
        self._update_title()
        self._fit()

    def _export_png(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(self, "PNG 내보내기", "도면.png", "PNG (*.png)")
        if fn:
            exporter.export_png(self.editor.doc, fn, scale=3.0)

    def _export_svg(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(self, "SVG 내보내기", "도면.svg", "SVG (*.svg)")
        if fn:
            exporter.export_svg(self.editor.doc, fn)


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

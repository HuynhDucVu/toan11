from typing import Sequence
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget
from ..core.parser import Question


class WhiteboardOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pen_color, self.pen_width, self.eraser_mode = QColor("#D93025"), 3, False
        self._strokes: list[tuple[QColor, int, list[QPoint]]] = []
        self._active: list[QPoint] | None = None

    def undo(self) -> None:
        if self._strokes:
            self._strokes.pop()
            self.update()

    def clear_board(self) -> None:
        self._strokes.clear()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pt = event.position().toPoint()
            if self.eraser_mode:
                self._strokes = [st for st in self._strokes if all((p - pt).manhattanLength() > 18 for p in st[2])]
                self.update()
            else:
                self._active = [pt]
                self._strokes.append((QColor(self.pen_color), self.pen_width, self._active))
                self.update()

    def mouseMoveEvent(self, event):
        if self._active is not None:
            self._active.append(event.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, event):
        self._active = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for col, w, pts in self._strokes:
            if len(pts) >= 2:
                p.setPen(QPen(col, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                for i in range(1, len(pts)):
                    p.drawLine(pts[i - 1], pts[i])


class PresentationDialog(QDialog):
    def __init__(self, questions: Sequence[Question], start_index: int = 0, parent=None):
        super().__init__(parent)
        self.questions = list(questions)
        self.idx = max(0, min(start_index, len(self.questions) - 1)) if self.questions else 0
        self.show_solution = False
        self.setWindowTitle("Trình chiếu Chữa bài — F11 toàn màn hình")
        self.resize(1100, 720)
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.lbl = QLabel()
        b_prev, b_next, self.b_ans, b_pen, b_era, b_undo, b_clr, b_full = (
            QPushButton("◀ Trước"), QPushButton("Sau ▶"), QPushButton("Hiện đáp án"),
            QPushButton("Bút đỏ"), QPushButton("Tẩy"), QPushButton("Hoàn tác"), QPushButton("Xóa bảng"), QPushButton("F11"),
        )
        for w in (self.lbl, b_prev, b_next, self.b_ans, b_pen, b_era, b_undo, b_clr, b_full):
            bar.addWidget(w)
        root.addLayout(bar)
        self.viewer = QTextBrowser()
        self.viewer.setStyleSheet("font-size:20px;padding:18px;background:#fff;")
        root.addWidget(self.viewer, stretch=1)
        self.overlay = WhiteboardOverlay(self.viewer)
        self.overlay.hide()
        b_prev.clicked.connect(lambda: self._step(-1))
        b_next.clicked.connect(lambda: self._step(1))
        self.b_ans.clicked.connect(self._toggle_sol)
        b_pen.clicked.connect(lambda: self._board(False))
        b_era.clicked.connect(lambda: self._board(True))
        b_undo.clicked.connect(self.overlay.undo)
        b_clr.clicked.connect(self.overlay.clear_board)
        b_full.clicked.connect(self._toggle_fs)
        QShortcut(QKeySequence(Qt.Key_F11), self, activated=self._toggle_fs)
        self._render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.viewer.rect())

    def _toggle_fs(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _board(self, eraser: bool):
        self.overlay.eraser_mode = eraser
        self.overlay.show()
        self.overlay.raise_()

    def _toggle_sol(self):
        self.show_solution = not self.show_solution
        self.b_ans.setText("Ẩn lời giải" if self.show_solution else "Hiện đáp án")
        self._render()

    def _step(self, d: int):
        if self.questions:
            self.idx = (self.idx + d) % len(self.questions)
            self.show_solution = False
            self.overlay.clear_board()
            self._render()

    def _render(self):
        if not self.questions:
            self.viewer.setPlainText("Chưa có câu hỏi.")
            return
        q = self.questions[self.idx]
        self.lbl.setText(f"Câu {self.idx + 1}/{len(self.questions)} [{q.primary_id or q.qtype}]")
        lines = [f"<b>Câu {self.idx + 1}:</b> {q.stem}"]
        if q.qtype == "TN":
            for i, (c, ok) in enumerate(zip(q.choices, q.correct)):
                st = " style='color:#D93025;font-weight:bold;'" if (self.show_solution and ok) else ""
                lines.append(f"<div{st}><b>{'ABCD'[i]}.</b> {c}</div>")
        elif q.qtype == "DS":
            for i, (c, ok) in enumerate(zip(q.choices, q.correct)):
                tg = f" <b>({'ĐÚNG' if ok else 'SAI'})</b>" if self.show_solution else ""
                lines.append(f"<div><b>{'abcd'[i]})</b> {c}{tg}</div>")
        elif q.qtype == "KQ" and self.show_solution:
            lines.append(f"<div style='color:#188038'><b>Đáp số:</b> {q.short_ans}</div>")
        if self.show_solution and q.solution:
            lines.append(f"<hr/><b>Lời giải:</b><br/>{q.solution}")
        self.viewer.setHtml("<br/>".join(lines))

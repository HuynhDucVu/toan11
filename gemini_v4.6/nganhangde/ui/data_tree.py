from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem


def _dot(hex_color: str) -> QIcon:
    pm = QPixmap(12, 12)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setBrush(QColor(hex_color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, 10, 10)
    p.end()
    return QIcon(pm)


class WorkspaceDataTree(QTreeWidget):
    action_triggered = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabel("Cây dữ liệu đề thi")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def load_nodes(self, rows: list[dict]) -> None:
        self.clear()
        imap = {r["id"]: QTreeWidgetItem([r["name"]]) for r in rows}
        for r in rows:
            it = imap[r["id"]]
            it.setData(0, Qt.UserRole, r["id"])
            pid = r.get("parent_id")
            if pid and pid in imap:
                imap[pid].addChild(it)
            else:
                self.addTopLevelItem(it)
        self.expandAll()

    def _menu(self, pos) -> None:
        item = self.itemAt(pos)
        if not item:
            return
        nid = int(item.data(0, Qt.UserRole))
        menu = QMenu(self)
        for key, lbl, col in [
            ("open_view", "Mở / Xem trước", "#1A73E8"),
            ("export_copy", "Sao chép / Xuất tệp", "#188038"),
            ("grade_key", "Chấm điểm / Đáp án", "#8430CE"),
            ("send_result", "Gửi kết quả", "#E37400"),
            ("delete_node", "Xóa mục này", "#D93025"),
        ]:
            act = QAction(_dot(col), lbl, self)
            act.triggered.connect(lambda _=False, k=key, i=nid: self.action_triggered.emit(k, i))
            menu.addAction(act)
        menu.exec(self.viewport().mapToGlobal(pos))

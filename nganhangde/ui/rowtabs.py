"""Thanh tab chính chia thành nhiều hàng (tránh tràn ngang).

QTabWidget vẫn giữ toàn bộ trang (count, widget, indexOf, setCurrentWidget… không đổi); thanh tab mặc định bị ẩn và
thay bằng một QTabBar cho mỗi hàng. Chọn tab ở hàng nào cũng chuyển trang và làm sáng đúng tab đó."""
from __future__ import annotations

from PySide6.QtWidgets import QTabBar, QTabWidget, QVBoxLayout, QWidget


class RowTabWidget(QTabWidget):
    def __init__(self):
        super().__init__()
        self._bars: list[tuple[QTabBar, list[int]]] = []
        self._host = None
        self._syncing = False
        self.tabBar().hide()
        self.currentChanged.connect(self._sync)

    def install_rows(self, rows: list[list[int]]) -> QWidget:
        """rows: danh sách hàng, mỗi hàng là danh sách chỉ số trang. Trả về widget chứa các hàng và trang —
        đặt widget này làm widget trung tâm của cửa sổ."""
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        for idxs in rows:
            bar = QTabBar()
            bar.setObjectName("rowBar")
            bar.setProperty("active", False)
            bar.setExpanding(False)
            bar.setDrawBase(False)
            for i in idxs:
                bar.addTab(self.tabText(i))
            bar.currentChanged.connect(lambda k, b=bar: self._picked(b, k))
            lay.addWidget(bar)
            self._bars.append((bar, idxs))
        lay.addWidget(self)
        self._host = host
        self._sync(self.currentIndex())
        return host

    def _picked(self, bar: QTabBar, k: int):
        if self._syncing or k < 0:
            return
        for b, idxs in self._bars:
            if b is bar and k < len(idxs):
                self.setCurrentIndex(idxs[k])
                return

    def _sync(self, idx: int):
        """Làm sáng tab của trang đang mở ở hàng chứa nó. Hàng còn lại vẫn giữ tab cũ nhưng bị làm nhạt
        (Qt không cho bỏ chọn một QTabBar nên dùng thuộc tính «active» trong stylesheet)."""
        self._syncing = True
        try:
            for bar, idxs in self._bars:
                if idx in idxs:
                    bar.setCurrentIndex(idxs.index(idx))
                active = idx in idxs
                if bar.property("active") != active:
                    bar.setProperty("active", active)
                    bar.style().unpolish(bar)
                    bar.style().polish(bar)
        finally:
            self._syncing = False


def find_page(tabs: QTabWidget, text: str) -> int:
    """Chỉ số trang có tên chứa «text» (bỏ qua biểu tượng và dấu &)."""
    for i in range(tabs.count()):
        if text.replace("&", "") in tabs.tabText(i).replace("&", ""):
            return i
    raise KeyError(text)

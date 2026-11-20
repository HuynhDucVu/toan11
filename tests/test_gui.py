"""Kiểm thử khói giao diện: mở mọi tab và hộp thoại chính, chạy các thao tác tiêu biểu (không cần màn hình).

Mục đích: bảo vệ khi tái cấu trúc mã giao diện – lỗi import/thiếu tên/sai chữ kí sẽ lộ ra ngay.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QSettings  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(__file__))
SAMPLE = os.path.join(ROOT, "0-1-De-chuan-hoa-1.tex")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path_factory.mktemp("settings")))
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.information = staticmethod(lambda *x, **k: None)
    QMessageBox.warning = staticmethod(lambda *x, **k: None)
    QMessageBox.question = staticmethod(lambda *x, **k: QMessageBox.StandardButton.Yes)
    return a


@pytest.fixture()
def win(app, tmp_path):
    from nganhangde import gui_qt
    from nganhangde.parser import parse_file
    w = gui_qt.MainWindow(str(tmp_path / "kho.db"))
    for q in parse_file(SAMPLE):
        w.bank.add(q)
    w.build_tree()
    w.refresh()
    yield w
    w.close()


def test_main_tabs_and_panels(win, app, tmp_path):
    from nganhangde import gui_qt
    assert win.table.rowCount() == 22
    for i in range(win.main_tabs.count()):
        win.main_tabs.setCurrentIndex(i)
        app.processEvents()
    win.table.selectRow(0)
    win.on_select()
    assert "Câu #" in win.info.toPlainText()
    # rà soát
    win.review_panel.run()
    assert win.review_panel.t.rowCount() >= 1
    # sinh câu
    p = win.gen_q_panel
    p.sp_n.setValue(3)
    p.e_seed.setText("1")
    p.run()
    assert len(p.qs) == 3
    # vẽ hình
    d = win.draw_panel
    d.bbt_auto()
    assert "tkzTabVar" in d.code.toPlainText()
    d.graph()
    d.chart()
    assert "\\begin{tikzpicture}" in d.code.toPlainText()
    # thống kê, công cụ
    win.stats_panel.reload()
    win.tools_panel.files.addItem(SAMPLE)
    win.tools_panel.get_answers()
    assert "Bảng đáp án" in win.tools_panel.out.toPlainText()
    # tạo đề (không mở hộp kết quả)
    gui_qt.ResultDialog.exec = lambda self: 0
    gp = win.gen_panel
    gp.t.setRowCount(0)
    for r in ({"qtype": "TN", "id": "*", "count": 12}, {"qtype": "DS", "id": "*", "count": 4},
              {"qtype": "KQ", "id": "*", "count": 6}):
        gp.add_row(r)
    gp.c_preview.setChecked(False)
    gp.c_pdf.setChecked(False)
    gp.e_ma.setText("101, 102")
    gp.e_out[0].setText(str(tmp_path / "de"))
    gp.generate()
    assert os.path.exists(tmp_path / "de" / "de_101.tex")


def test_dialogs_open(win, app):
    from nganhangde import gui_qt, updater
    from nganhangde.generator import Rule, pick_questions
    import random
    qs = win.bank.search()
    dialogs = [
        gui_qt.EditDialog(win, qs[0].db_id),
        gui_qt.EditDialog(win, None),
        gui_qt.IdMapDialog(win),
        gui_qt.AssignIdDialog(win, qs[:5], [f"#{q.db_id}" for q in qs[:5]]),
        gui_qt.PdfSettingsDialog(win),
        gui_qt.GeminiSettingsDialog(win),
        gui_qt.UpdateDialog(win, updater.Release("99.0.0", "## Mới\n- x", "https://x")),
    ]
    rules = [Rule("TN", 3)]
    dialogs.append(gui_qt.SwapDialog(win.gen_panel, pick_questions(win.bank, rules, random.Random(0)), rules))
    from nganhangde.pdfbuild import BuildResult
    dialogs.append(gui_qt.PdfResultDialog(win, [BuildResult("a.tex", False, errors=["Dòng 3: lỗi"])]))
    for dlg in dialogs:
        dlg.show()
        app.processEvents()
        dlg.close()
    a = dialogs[3]
    a.picker.cbs[0].setCurrentIndex(0)
    a.compute()                                   # gợi ý theo kho (không cần Map ID)


def test_batches_history_and_avoid(win, app, tmp_path):
    from nganhangde import gui_qt
    gui_qt.ResultDialog.exec = lambda self: 0
    gp = win.gen_panel
    gp.t.setRowCount(0)
    gp.add_row({"qtype": "TN", "id": "*", "count": 5})
    gp.c_preview.setChecked(False)
    gp.c_pdf.setChecked(False)
    gp.e_ma.setText("101")
    gp.e_out[0].setText(str(tmp_path / "d1"))
    gp.generate()
    first = win.bank.recent_question_ids(1)
    assert len(first) == 5
    gp.sp_recent.setValue(1)
    gp.e_out[0].setText(str(tmp_path / "d2"))
    gp.generate()
    second = win.bank.recent_question_ids(1)
    assert len(second) == 5 and not (first & second)
    assert len(win.bank.batches()) == 2
    from PySide6.QtWidgets import QDialog
    QDialog.exec = lambda self: 0
    win.show_batches()
    d = gui_qt.IdMapDialog(win)
    d.load_builtin()
    assert "0D" in d.ed.toPlainText() or len(d.ed.toPlainText()) > 1000

"""Kiểm thử khói giao diện: mở mọi tab và hộp thoại chính, chạy các thao tác tiêu biểu (không cần màn hình).

Mục đích: bảo vệ khi tái cấu trúc mã giao diện – lỗi import/thiếu tên/sai chữ kí sẽ lộ ra ngay.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QSettings, Qt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(__file__))
SAMPLE = os.path.join(ROOT, "0-1-De-chuan-hoa-1.tex")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    d = str(tmp_path_factory.mktemp("settings"))
    for fmt in (QSettings.Format.IniFormat, QSettings.Format.NativeFormat):   # app dùng NativeFormat
        QSettings.setPath(fmt, QSettings.Scope.UserScope, d)
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
    win.bbt_panel.bbt_auto()
    assert "tkzTabVar" in win.bbt_panel.code.toPlainText()
    d = win.graph_panel
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


def test_phase2_options(win, app, tmp_path, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda *a: True))
    o = win.gen_panel.opts
    o.e_kq.setText("0,25")
    o.e_tl.setText("1; 0,5")
    o.c_qr.setChecked(True)
    o.mix.sp_run.setValue(2)
    e = win.gen_panel.export_options()
    assert e.diem, (o.e_tn.text(), o.e_ds.text(), o.e_kq.text(), o.l_diem.text())
    assert e.scoring_obj().kq == 0.25 and e.qr_answers
    assert o.mix_options().max_run == 2
    o.e_ds.setText("1;2")                       # sai ⇒ không dùng thang tuỳ chỉnh
    assert o.export_options().diem is None
    o.save()
    p = tmp_path / "mt.xlsx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(p), "")))
    win.gen_panel.export_cv7991()
    assert p.exists()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(p), "")))
    n = win.gen_panel.t.rowCount()
    win.gen_panel.load_matrix()
    assert win.gen_panel.t.rowCount() == n


def test_ai_assistant(win, app, monkeypatch):
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from test_v13_ai import TN, Fake
    from nganhangde.ui.dialogs import ai_assistant, ai_settings
    s = ai_settings.AiSettingsDialog(win)
    s.cb_prov.setCurrentIndex(s.cb_prov.findData("claude"))
    s.e_key.setText("k")
    s.save()
    assert win.settings.value("ai/provider") == "claude" and win.settings.value("ai/claude_key") == "k"
    win.settings.setValue("ai/provider", "gemini")
    monkeypatch.setattr(ai_assistant, "ensure_client", lambda w: Fake([TN, TN]))
    d = ai_assistant.AiAssistantDialog(win)
    win.table.selectRow(0)
    d.sp_sim.setValue(2)
    d.run_similar()
    assert d.t.rowCount() == 2 and "\\begin{ex}" in d.view.toPlainText()
    n = win.bank.count()
    d.add_to_bank()
    assert win.bank.count() == n + 1                     # 2 câu giống nhau ⇒ 1 câu bị coi là trùng
    d.check_gaps()
    d.e_ans.setPlainText("x = 1")
    d.e_q.setPlainText("Giải phương trình")
    d.run_grade()
    assert "0,75" in d.grade_view.toPlainText() or "0.75" in d.grade_view.toPlainText()


def test_draw_studio(win, app):
    s = win.sol_panel
    s.numline()
    assert "tikzpicture" in s.code.toPlainText()
    s.region()
    assert "GTLN" in s.region_info.toPlainText()
    s.trig()
    assert "circle" in s.code.toPlainText()
    v = win.solid_panel
    v.cb_solid.setCurrentIndex(v.cb_solid.findData("lap_phuong"))
    v.solid()
    assert "(Dp)" in v.code.toPlainText()
    b = win.bbt_panel
    b.sign_auto()
    assert "tkzTabLine" in b.code.toPlainText()
    d = win.graph_panel
    d.e_ext.setText("-1;3;1;-1")
    d.from_extrema()
    assert d.e_gx.text() == "x^3 - 3x + 1"
    d.e_xt.setText("-1, 1")
    d.graph()
    assert "dashed] (-1,0)" in d.code.toPlainText()
    d.e_gx.setText("(x^2+1)/(x-1)")
    d.e_guides.setText("")
    d.e_xt.setText("")
    d.e_shade.setText("2; 3")
    d.graph()
    assert "x=1" in d.code.toPlainText() and "blue!20" in d.code.toPlainText()


def test_arena_dialog_and_present(win, app, monkeypatch, tmp_path):
    from PySide6.QtGui import QDesktopServices
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda u: opened.append(u.toString()) or True))
    from nganhangde.ui.dialogs.arena import ArenaDialog
    d = ArenaDialog(win)
    d.cb_src.setCurrentIndex(1)
    d.e_file.setText(SAMPLE)
    d.sp_port.setValue(0 or 8790)
    d.toggle()
    assert d.arena is not None and "8790" in d.l_url.text()
    d.refresh()
    d.toggle()
    assert d.arena is None
    win.table.selectRow(0)
    win.present()
    assert opened and opened[-1].endswith("trinh_chieu.html")
    win.tree.setCurrentItem(win.tree.topLevelItem(0))


def test_new_tabs(win, app, monkeypatch, tmp_path):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QFileDialog
    from nganhangde import gui_qt
    gui_qt.ResultDialog.exec = lambda self: 0
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda *a: True))
    assert win.main_tabs.count() == 10
    win.show_panel(win.similar_panel)
    assert win.current_panel() is win.similar_panel
    win.gen_panel.e_out[0].setText(str(tmp_path / "out"))
    win.gen_panel.c_pdf.setChecked(False)
    win.table.selectAll()
    win.pick_panel.add_selected()
    assert len(win.pick_panel.basket) == 22
    win.pick_panel.sp_n.setValue(2)
    win.pick_panel.generate()
    assert (tmp_path / "out" / "de_101.tex").exists() or any((tmp_path / "out").glob("de_*.tex"))
    win.filemix_panel.e_file.setText(SAMPLE)
    win.filemix_panel.generate()
    win.similar_panel.e_file.setText(SAMPLE)
    win.similar_panel.generate()
    win.matrix_panel.reload()
    assert win.matrix_panel.t.rowCount() >= 1
    g = win.geom_panel
    g.cb_tpl.setCurrentIndex(1)
    g.load_template()
    assert "tikzpicture" in g.code.toPlainText()
    g.cb_kind.setCurrentIndex(g.cb_kind.findData("trung_diem"))
    g.edits["ten"].setText("M")
    g.edits["A"].setText("B")
    g.edits["B"].setText("C")
    g.add_step()
    assert "M" in g.view.scene.pts
    c = win.convert_panel
    c.e_files.setText(SAMPLE)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(tmp_path / "x.txt"), "")))
    c.aiken()
    assert "ANSWER" in (tmp_path / "x.txt").read_text(encoding="utf-8")
    e = win.editor_panel
    e.insert(open(SAMPLE, encoding="utf-8").read())
    e.review()
    assert "câu" in e.out.toPlainText()
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([SAMPLE], "")))
    main = win.bank.path
    win.view_files()
    assert win.file_mode and win.bank.path != main and win.table.rowCount() == 22
    assert any(win.table.item(r, 6).text() for r in range(win.table.rowCount()))
    win.back_to_bank()
    assert win.bank.path == main and not win.file_mode


def test_editor_ai(win, app, monkeypatch):
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from test_v13_ai import TN, FakeSolver
    from nganhangde.ui.dialogs import ai_assistant
    monkeypatch.setattr(ai_assistant, "ensure_client", lambda w: FakeSolver("B"))
    monkeypatch.setattr(ai_assistant.AiAssistantDialog, "exec", lambda self: self._auto())
    e = win.editor_panel
    e.ed.setPlainText(TN.replace("\\loigiai{$x>1$. Chọn đáp án B.}", "\\loigiai{}"))

    def auto(self):
        self.run_solution()
        self.to_editor()
        return 1
    ai_assistant.AiAssistantDialog._auto = auto
    e.ai(6)
    assert "Ta có $x>1$" in e.ed.toPlainText()


def test_id_grid_and_online_settings(win, app):
    g = win.idgrid_panel
    g.reload()
    assert g.t.rowCount() > 0
    g.cb_quick.setCurrentIndex(g.cb_quick.findData("H"))
    g.sp_quick.setValue(1)
    g.quick_fill()
    rd = g.rules()
    assert rd and all(r["muc_do"] == "H" and r["count"] == 1 for r in rd)
    assert g.to_matrix(True) and win.gen_panel.t.rowCount() == len(rd)
    r0 = next(r for r in range(g.t.rowCount()) if g.t.item(r, 4).flags() & Qt.ItemFlag.ItemIsEditable)
    g.t.item(r0, 4).setText("99")                 # vượt số câu có ⇒ tự hạ xuống
    key = g._shown[r0][0]
    assert g.counts[key]["N"] == g._shown[r0][3]["N"]
    from nganhangde.ui.dialogs.online_settings import OnlineSettingsDialog, load
    d = OnlineSettingsDialog(win)
    d.e_link.setText("https://docs.google.com/forms/d/e/FORMID/viewform?entry.5=TEN&entry.6=DIEM")
    import nganhangde.ui.dialogs.online_settings as os_
    os_.QMessageBox.information = staticmethod(lambda *a, **k: None)
    d.read_link()
    d.colors["khung"].setText("#123456")
    d.save()
    style, gform = load(win.settings)
    assert style == {"khung": "#123456"} and gform["entries"] == {"ten": "5", "diem": "6"}
    assert win.gen_panel.export_options().gform["id"] == "FORMID"


def test_seed_sample_and_welcome(win, app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from nganhangde.db import Bank
    win.open_bank(str(win.bank.path) + "_trong.db")          # kho mới, trống
    assert win.bank.count() == 0
    called = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: called.append(1))
    monkeypatch.delenv("NHD_NO_WELCOME", raising=False)
    win.welcome_if_empty()
    assert called                                           # có hiện hướng dẫn khi kho trống
    win.seed_sample()                                       # QMessageBox.question đã giả lập trả về Yes
    assert win.bank.count() > 90 and isinstance(win.bank, Bank)
    called.clear()
    win.welcome_if_empty()
    assert not called                                       # kho có câu thì không hiện


def test_word_to_tex_dialog(win, app, monkeypatch, tmp_path):
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from test_v17 import _make_docx, _p
    from PySide6.QtWidgets import QFileDialog
    from nganhangde.ui.dialogs.word2tex import Word2TexDialog, convert_word_file
    f = tmp_path / "de.docx"
    _make_docx(str(f), _p("Câu 1. Tính $x$.") + _p("A. 1") + _p("B. 2", underline=True) + _p("C. 3") + _p("D. 4"))
    d = Word2TexDialog(win)
    d.e_rep.setPlainText("Tính = Giải")
    d._ok()
    tex, notes = convert_word_file(win, str(f), d)
    assert "Giải $x$." in tex and "\\True 2" in tex
    monkeypatch.setattr(Word2TexDialog, "exec", lambda self: 1)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([str(f)], "")))
    win.show_panel(win.tools_panel)
    win.tools_panel.word_to_tex()
    assert (tmp_path / "de_tuWord.tex").exists()

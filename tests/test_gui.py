"""Kiểm thử khói giao diện: mở mọi tab và hộp thoại chính, chạy các thao tác tiêu biểu (không cần màn hình).

Mục đích: bảo vệ khi tái cấu trúc mã giao diện – lỗi import/thiếu tên/sai chữ kí sẽ lộ ra ngay.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


from PySide6.QtCore import QSettings, Qt  # noqa: E402
from nganhangde.parser import parse_file  # noqa: E402

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
    assert win.main_tabs.count() == 11
    win.show_panel(win.similar_panel)
    assert win.current_panel() is win.similar_panel
    win.gen_panel.e_out[0].setText(str(tmp_path / "out"))
    win.gen_panel.c_pdf.setChecked(False)
    win.table.selectAll()
    win.pick_panel.add_selected()
    assert len(win.pick_panel.basket) == 22
    win.opt_panel.cb_n.setCurrentIndex(win.opt_panel.cb_n.findData(2))
    win.pick_panel.generate()
    assert (tmp_path / "out" / "de_101.tex").exists() or any((tmp_path / "out").glob("de_*.tex"))
    win.filemix_panel.set_files([SAMPLE])
    win.filemix_panel.generate()
    win.similar_panel.e_file.setText(SAMPLE)
    win.similar_panel.sample = parse_file(SAMPLE)
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
    r0 = next(r for r in range(g.t.rowCount()) if g.t.item(r, 8).flags() & Qt.ItemFlag.ItemIsEditable)
    g.t.item(r0, 8).setText("99")                 # vượt số câu có ⇒ tự hạ xuống
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
    d.rep_add("Tính", "Giải")
    d._ok()
    tex, notes = convert_word_file(win, str(f), d)
    assert "Giải $x$." in tex and "\\True 2" in tex
    monkeypatch.setattr(Word2TexDialog, "exec", lambda self: 1)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([str(f)], "")))
    win.show_panel(win.tools_panel)
    win.tools_panel.word_to_tex()
    from nganhangde.appdirs import folder
    out = os.path.join(folder("word2extest"), "de_tuWord.tex")
    assert os.path.exists(out) and not (tmp_path / "de_tuWord.tex").exists()     # lưu ở DATA\\WORD2EXTEST, không cạnh file Word


def test_import_wizard(win, app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox
    from nganhangde.ui.dialogs.import_wizard import ImportWizard
    tex = (r"\begin{ex}%[0D2N1-2]" "\nTính $1+1$.\n\\choice\n{$1$}\n{\\True $2$}\n{$3$}\n{$4$}\n"
           r"\loigiai{Chọn B.}" "\n" r"\end{ex}" "\n\n"
           r"\begin{ex}%[0D2N1-3]" "\nTính $2+2$.\n\\choice\n{$1$}\n{$2$}\n{\\True $4$}\n{$5$}\n\\end{ex}\n")
    f = tmp_path / "a.tex"
    f.write_text(tex, encoding="utf-8")
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: 0))
    before = win.bank.count()
    d = ImportWizard(win, [str(f)])
    d.cks["need_solution"].setChecked(True)
    d.step1()
    assert [bool(e.skip) for e in d.entries] == [False, True]
    out = tmp_path / "fix.tex"
    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    d.export()
    assert out.exists()
    d.step3()
    assert win.bank.count() == before + 1


def test_pdf_preview(win, app):
    from nganhangde.phieutltn import template_path
    from nganhangde.ui.dialogs.pdf_preview import PdfPreviewDialog, page_count
    pdf = template_path()                      # phiếu TLTN đi kèm (không phụ thuộc LaTeX trên máy)
    assert page_count(pdf) == 1
    d = PdfPreviewDialog(win, pdf)
    assert d.lb.pixmap() is not None and not d.lb.pixmap().isNull()


def test_update_panel(win, app, monkeypatch):
    import time
    from nganhangde import __version__, updater
    p = win.update_panel
    assert win.main_tabs.indexOf(p) >= 0 and "Bạn đang dùng bản " + __version__ in p.head.text()
    new = updater.Release("99.0.0", "## Mới\n- tính năng", "https://example.com/r", "https://example.com/x.exe", 1048576, "")
    p.apply_release(new)
    assert "99.0.0" in p.status.text() and "tính năng" in p.notes.toPlainText()
    assert not p.b_go.isEnabled()                       # chạy từ mã nguồn (không phải .exe) ⇒ không tự cập nhật
    assert p.b_skip.isEnabled()
    p.skip()
    assert win.settings.value("update/skip") == "99.0.0"
    same = updater.Release(__version__, "", "https://example.com/r")
    p.apply_release(same)
    assert "mới nhất" in p.status.text() and not p.b_skip.isEnabled()
    monkeypatch.setattr(updater, "latest_release", lambda: new)
    p.check()
    t = time.time()
    while "99.0.0" not in p.status.text() and time.time() - t < 10:
        app.processEvents()
        time.sleep(0.05)
    assert "99.0.0" in p.status.text()
    # mở lúc khởi động: không bật «tự tải» ⇒ để hộp thông báo cũ xử lý
    win.settings.setValue("update/skip", "")
    assert p.on_startup(new) is False


def test_run_word_to_tex_summary(win, app, tmp_path):
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from test_v17 import _make_docx, _p
    from nganhangde.ui.dialogs.word2tex import Word2TexDialog, run_word_to_tex, summary_html
    good, empty = tmp_path / "tot.docx", tmp_path / "rong.docx"
    _make_docx(str(good), _p("Câu 1. Tính.") + _p("A. 1") + _p("B. 2", underline=True) + _p("C. 3") + _p("D. 4"))
    _make_docx(str(empty), _p("Chỉ có một đoạn văn không phải câu hỏi."))
    d = Word2TexDialog(win)
    assert d.engine() == "direct" and d.options().ds
    res = run_word_to_tex(win, [str(good), str(empty), str(tmp_path / "khong_co.docx")], d)
    assert [r["n"] for r in res[:2]] == [1, 0] and res[2]["error"]
    html = summary_html(res)
    assert "tot.docx" in html and "→ <b>1</b> câu" in html and "→ <b>0</b> câu" in html and "chan_doan_rong" in html


def test_word2tex_dialog_like_mylt(win, app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from nganhangde.ui.dialogs.word2tex import Word2TexDialog
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: 0))
    win.settings.remove("w2t/rep")                           # cài đặt dùng chung cả phiên kiểm thử
    d = Word2TexDialog(win)
    assert [d.radios[k].text() for k in ("convert", "toggle", "mathpix", "gemini")] == [
        "Dùng Convert Equations", "Dùng Toggle TeX", "Dùng Mathpix API", "Dùng Gemini"]
    assert d.windowTitle() == "Tuỳ chọn chuyển Word/PDF sang TeX" and not d.cb_type.isEnabled()
    assert {d.boxes[k].text() for k in d.boxes} == {"Chuyển hình", "Chuyển bảng", "Chuyển câu ĐS", "Chuyên đề", "Môn Hoá", "AI rà soát đáp án & viết lại lời giải theo mẫu LaTeX"}
    d.radios["toggle"].setChecked(True)
    d.e_mid.setText("id1")
    d.e_mkey.setText("key1")
    d.e_gkey.setText("gk")
    d.boxes["ds"].setChecked(False)
    d.rep_add("Δ", "\\Delta")
    d.rep_add("x", "y")
    d.t.selectRow(1)
    d.rep_del()
    d.g_rep.setChecked(True)
    d._ok()
    assert win.settings.value("w2t/engine2") == "toggle" and win.settings.value("mathpix/app_id") == "id1"
    assert win.settings.value("ai/key") == "gk" and d.replacements() == [("Δ", "\\Delta")] and not d.options().ds
    d2 = Word2TexDialog(win)                                 # mở lại: nhớ lựa chọn, bảng thay thế
    assert d2.engine() == "toggle" and d2.replacements() == [("Δ", "\\Delta")]
    d2.g_rep.setChecked(False)
    assert d2.replacements() == []


def test_mix_tab_like_mylt(win, app, tmp_path):
    from nganhangde.ui.tabs.id_grid import COLS
    mix = win.main_tabs.widget(0)
    assert [mix.inner_tabs.tabText(i) for i in range(mix.inner_tabs.count())] == [
        "Tạo đề theo ID", "Tạo đề tự chọn", "Tạo đề theo file", "Tạo đề tương tự", "Tuỳ chọn đề", "Nâng cao (ma trận…)"]
    bar = win.mix_source_bar
    assert bar.r_bank.text() == "Từ ngân hàng câu hỏi" and bar.r_files.text().startswith("Từ Files.")
    assert bar.b_open.text() == "Mở ngân hàng" and bar.b_import.text() == "Nhập câu hỏi"
    assert COLS[:8] == ["STT", "ID", "Lớp", "Môn", "Chương", "Bài, dạng", "Loại", "Đã có (N/H/V/C)"]
    g = win.idgrid_panel
    g.reload()
    n_all = g.t.rowCount()
    assert n_all > 0 and g.t.item(0, 0).text() == "1" and "?" in g.t.item(0, 1).text()
    # Chọn nhanh: lọc theo loại rồi «Lấy» 2 câu mức H
    g.q["loai"].setCurrentIndex(g.q["loai"].findData("TN"))
    g.q["muc"].setCurrentIndex(g.q["muc"].findData("H"))
    g.sp_n.setCurrentIndex(g.sp_n.findData(2))
    g.apply_filter()
    assert 0 < g.t.rowCount() <= n_all and all(g.t.item(r, 6).text() == "TN" for r in range(g.t.rowCount()))
    g.take_quick()
    assert g.rules() and all(r["qtype"] == "TN" and r["muc_do"] == "H" and r["count"] <= 2 for r in g.rules())
    # Từ Files: kho tạm nạp từ file, bảng tải các câu trong file
    f = tmp_path / "nguon.tex"
    f.write_text("\\begin{ex}%[0D9N1-1]\nCâu A $1$\n\\choice\n{\\True 1}\n{2}\n{3}\n{4}\n\\end{ex}\n"
                 "\\begin{ex}%[0D9H1-2]\nCâu B $2$\n\\choice\n{1}\n{\\True 2}\n{3}\n{4}\n\\end{ex}\n", encoding="utf-8")
    bar.load_files([str(f)])
    bar.r_files.setChecked(True)
    assert win.mix_source == "files" and win.pool_bank().count() == 2 and win.bank.count() > 2
    g.clear_counts()
    for k in ("loai",):
        g.q[k].setCurrentIndex(0)
    g.q["muc"].setCurrentIndex(0)
    g.apply_filter()
    assert g.t.rowCount() == 2
    bar.r_bank.setChecked(True)
    assert win.mix_source == "bank" and win.pool_bank() is win.bank


def test_pick_panel_source_table(win, app):
    p = win.pick_panel
    p.reload()
    assert p.t.rowCount() > 3 and "câu" in p.l_count.text() and p.total >= p.t.rowCount()
    assert [p.t.horizontalHeaderItem(c).text() for c in range(5)] == ["STT", "Nội dung câu hỏi", "Loại", "ID", "Chọn"]
    p.f["qtype"].setCurrentIndex(p.f["qtype"].findData("TN"))
    p.reload()
    assert all(p.t.item(r, 2).text() == "TN" for r in range(p.t.rowCount()))
    for r in (0, 1):
        p.t.item(r, 4).setCheckState(Qt.CheckState.Checked)
    assert len(p.basket) == 2 and p.l_count.text() == "Đã chọn: 2 câu"
    p.reload(keep_page=True)                                 # đổi trang/lọc lại vẫn nhớ câu đã chọn
    assert len(p.basket) == 2 and p.t.item(0, 4).checkState() == Qt.CheckState.Checked
    p.clear_chosen()
    assert not p.basket
    p.cb_n.setCurrentIndex(p.cb_n.findData(5))
    p.pick_random()
    assert len(p.basket) == 5


def test_pick_panel_paging(win, app):
    p = win.pick_panel
    p.PAGE = 5
    p.reload()
    n = p.total
    assert n > 5 and p.pages() == -(-n // 5)
    first = p.t.item(0, 1).text()
    p.go_page(1)
    assert p.page == 1 and p.t.item(0, 0).text() == "6" and p.t.item(0, 1).text() != first
    p.go_page(99)
    assert p.page == p.pages() - 1


def test_filemix_table_and_similar_panel(win, app):
    fm = win.filemix_panel
    fm.set_files([SAMPLE])
    assert [fm.t.horizontalHeaderItem(c).text() for c in range(4)] == ["STT", "Tập tin", "Đã có", "Lấy"]
    have = int(fm.t.item(0, 2).text())
    assert fm.l_count.text() == f"Đã chọn: {have} câu"
    fm.t.item(0, 3).setText("3")
    assert fm.l_count.text() == "Đã chọn: 3 câu" and len(fm.load_questions()) == 3
    fm.clear_take()
    assert fm.l_count.text() == f"Đã chọn: {have} câu"
    sp = win.similar_panel
    assert [sp.t.horizontalHeaderItem(c).text() for c in range(4)] == ["STT", "Câu hỏi đề gốc", "Câu hỏi đề tương tự", "Chọn"]
    sp.sample = parse_file(SAMPLE)
    sp.search()
    assert sp.t.rowCount() == len(sp.sample)


def test_options_panel_syncs_generator(win, app):
    op, gp = win.opt_panel, win.gen_panel
    op.cb_n.setCurrentIndex(op.cb_n.findData(6))
    op.e_truong.setText("THPT Thử")
    op.ck["giu_nguyen"].setChecked(True)
    op.cb_xlsx.setCurrentIndex(op.cb_xlsx.findText("Bảng ngang"))
    op.e_file_name.setText("KT15p")
    assert gp.e_n.value() == 6 and gp.e_truong.text() == "THPT Thử"
    assert not gp.opts.mix.boxes["shuffle_q"].isChecked() and gp.opts.cb_layout.currentData() == "ngang"
    assert gp.export_options().file_name == "KT15p"


def test_idgrid_pager_buttons_and_bottom_bar(win, app, monkeypatch):
    g = win.idgrid_panel
    g.reload()
    assert [b.text() for b in g.findChildren(type(g.b_first)) if b.text() in tuple("?HACEDOU")] == list("?HACEDOU")
    g.PAGE_SIZE = 5                                          # ép nhiều trang để thử Đầu/Trước/Sau/Cuối
    g.apply_filter()
    assert g.t.rowCount() == 5 and g.n_pages() >= 2 and g.cb_page.count() == g.n_pages()
    assert g.t.item(0, 0).text() == "1" and not g.b_prev.isEnabled() and g.b_next.isEnabled()
    g.b_next.click()
    assert g.t.item(0, 0).text() == "6" and g.b_prev.isEnabled()
    g.go_page(10 ** 9)
    assert g._page == g.n_pages() - 1 and not g.b_next.isEnabled()
    g.go_page(0)
    # lấy số câu ở trang 1, sang trang 2 vẫn giữ; U hoàn tác; C xoá hết
    r0 = next(r for r in range(g.t.rowCount()) if g.t.item(r, 8).flags() & Qt.ItemFlag.ItemIsEditable or
              g.t.item(r, 9).flags() & Qt.ItemFlag.ItemIsEditable or g.t.item(r, 10).flags() & Qt.ItemFlag.ItemIsEditable)
    col = next(c for c in range(8, 12) if g.t.item(r0, c).flags() & Qt.ItemFlag.ItemIsEditable)
    g.t.item(r0, col).setText("1")
    assert g.rules()
    g.go_page(1)
    assert g.rules()
    g.undo()
    assert not g.rules()
    g.t.item(0, 0)
    g.clear_counts()
    assert not g.rules()
    # nút «Tạo đề» và «Thoát» ở góc dưới tab Trộn đề
    called = []
    monkeypatch.setattr(g, "generate", lambda: called.append("id"))
    win.mix_tab.inner_tabs.setCurrentWidget(g)
    win.mix_generate()
    assert called == ["id"]
    texts = [b.text() for b in win.mix_tab.findChildren(type(g.b_first))]
    assert "Tạo đề" in texts and "Thoát" in texts


def test_idgrid_rows_for_files_without_id(win, app, tmp_path):
    import re
    t = re.sub(r"%\[[^\]]*\]", "", open(SAMPLE, encoding="utf-8").read())
    p = tmp_path / "khong_id.tex"
    p.write_text(t, encoding="utf-8")
    win.mix_source_bar.load_files([str(p)])
    win.mix_source = "files"
    g = win.idgrid_panel
    g.reload()
    assert g.rows and all(k[0] == "" for k, _, _ in g.rows)            # dòng «?» cho câu chưa có ID
    g.counts[g.rows[0][0]] = {"N": 2}
    rd = g.rules()
    assert rd and rd[0]["id"] == "?" and len(win.pool_bank().search(qtype=rd[0]["qtype"], id_like="?")) >= 1
    win.mix_source = "bank"
    g.reload_map()
    assert g.rows


def test_import_bank_dialog_and_file_load(win, app, monkeypatch):
    from nganhangde.ui.dialogs.import_bank import ImportBankDialog
    d = ImportBankDialog(win)
    assert {"Nhập", "Đóng", "Khởi tạo", "Sao lưu", "Kiểm tra", "Ghép", "Khôi phục", "Xoá lỗi", "Xuất",
            "Chuyển sang macOS, linux", "Hướng dẫn"} <= set(d.btn)
    d.paths = [SAMPLE]
    d.ck["deep_dups"].setChecked(True)
    d.cb_ratio.setCurrentIndex(d.cb_ratio.findData(0.7))
    d._save_opts()
    assert float(win.settings.value("iw/ratio")) == 0.7
    fm = win.filemix_panel
    fm.set_files([SAMPLE])
    fm.load_source()                                       # «Nạp vào nguồn»: chuyển sang chế độ Từ Files
    assert win.mix_source == "files" and win.pool_bank() is win.file_pool and win.file_pool.count() > 0
    win.mix_source_bar.r_bank.setChecked(True)
    assert win.pool_bank() is win.bank


def test_check_vs_clean_and_load_button_and_sheet_options(win, app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from nganhangde.ui.dialogs.import_bank import ImportBankDialog
    d = ImportBankDialog(win)
    seen = {}
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: seen.setdefault("q", a[2]) and QMessageBox.StandardButton.No))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: seen.setdefault("i", a[2])))
    n = win.bank.count()
    d.check()
    assert "Kho có" in seen["q"] and "không có câu nào bị xoá" in seen["q"].lower() and win.bank.count() == n
    d.clean()                                             # câu sai xoá được, câu hỏi hợp lệ không bị đụng
    assert win.bank.count() <= n
    bar = win.mix_source_bar
    bar.b_load.click()
    assert "Đã nạp lại" in win.statusBar().currentMessage()
    # tuỳ chọn phiếu: Chỉ đáp án + màu
    op = win.opt_panel
    op.sheet["chi_dap_an"].setChecked(True)
    op.cb_color.setCurrentText("Xanh")
    o = win.gen_panel.export_options()
    assert o.sheet_key_only and o.sheet_color == "Xanh"


def test_phieu_key_only(tmp_path):
    import random
    from nganhangde.generator import MixOptions, mix_versions, sections_from_questions
    from nganhangde.phieutltn import export_sheets
    vs = mix_versions(sections_from_questions(parse_file(SAMPLE)), ["0101"], random.Random(1), MixOptions())
    fs, _ = export_sheets(vs, str(tmp_path / "p"), key_only=True, color="Xanh", size="Đậm")
    assert all("trang" not in os.path.basename(f) for f in fs) and any("phieu_khoa_0101" in f for f in fs)


def test_draw_preview_single_window(win, app, monkeypatch):
    """Xem PDF: một cửa sổ duy nhất; mở lại thì cửa sổ cũ được đóng (không có hai cửa sổ cùng lúc)."""
    from nganhangde.appdirs import PHIEU_PDF
    from nganhangde.ui.dialogs import pdf_preview
    sp = win.sol_panel
    pdf = os.path.join(ROOT, "nganhangde", "data", PHIEU_PDF)
    d1 = pdf_preview.show_pdf(sp, pdf)
    d2 = pdf_preview.show_pdf(sp, pdf)
    assert d1 is not d2
    assert pdf_preview._OPEN["dlg"] is d2
    d2.close()
    assert sp.show_preview(pdf)
    assert pdf_preview._OPEN["dlg"] is not None



def test_draw_preview_without_latex(win, app, monkeypatch):
    """Máy không có LaTeX (CI Windows): tạo mã vẫn chạy, không ném lỗi EngineMissing ra ngoài."""
    import nganhangde.pdfbuild as pb
    def no_engine(*a, **k):
        raise pb.EngineMissing("thiếu LaTeX")
    monkeypatch.setattr(pb, "find_engine", no_engine)
    sp = win.sol_panel
    sp.sub.setCurrentIndex(0)
    sp.numline()                                              # auto=True: im lặng
    sp.preview_pdf()                                          # bấm tay: báo cho người dùng
    assert "Chưa tìm thấy LaTeX" in sp.l_pkg.text()


def test_hdsd_window(win, app, monkeypatch):
    """HDSD: mở từ menu Trợ giúp (F1), đủ mục chính, nút HDSD ở tab Tạo đề tự chọn mở đúng mục."""
    from nganhangde import hdsd_text
    from nganhangde.ui.dialogs.hdsd import HdsdDialog
    titles = [t for _g, t, _h in hdsd_text.TOPICS]
    for need in ("Nhập câu hỏi vào ngân hàng", "Tạo đề theo ID", "Tạo đề tự chọn", "Tạo đề theo file",
                 "Tạo đề tương tự", "Tuỳ chọn đề", "Dọn kho", "Trục số, miền nghiệm, đường tròn lượng giác"):
        assert need in titles, need
    assert all(len(h) > 80 for _g, _t, h in hdsd_text.TOPICS)
    conv = [t for g, t, _h in hdsd_text.TOPICS if g == "Chuyển đổi"]
    for need in ("Word/PDF → LaTeX", "Nhập ngân hàng MyLT", "Đề online: Moodle, Aiken, Quizizz, Forms, Blogger",
                 "Hình TikZ: ra PNG hoặc tách file"):
        assert need in conv, need
    monkeypatch.setattr(HdsdDialog, "exec", lambda self: 0)
    dlg = HdsdDialog(win, "Tạo đề tự chọn")
    assert dlg.nav.currentItem().text() == "Tạo đề tự chọn"
    assert "Tạo đề tự chọn" in dlg.body.toPlainText()
    assert dlg.open_topic("Tạo đề tương tự") and dlg.nav.currentItem().text() == "Tạo đề tương tự"
    assert win.pick_panel.help.__self__ is win.pick_panel            # nút HDSD tồn tại và được nối
    monkeypatch.setattr(HdsdDialog, "exec", lambda self: 0)
    win.show_hdsd()


def test_main_tabs_two_rows(win, app):
    """Thanh tab chính chia 2 hàng: chọn ở hàng nào cũng chuyển trang và làm sáng đúng tab."""
    from PySide6.QtWidgets import QTabBar
    mt = win.main_tabs
    bars = [b for b in win.centralWidget().findChildren(QTabBar) if b.objectName() == "rowBar"]
    assert len(bars) == 2
    assert bars[0].count() + bars[1].count() == mt.count() == 11
    row2 = bars[1]
    k = next(i for i in range(row2.count()) if "Câu hỏi" in row2.tabText(i))
    row2.setCurrentIndex(k)
    assert "Câu hỏi" in mt.tabText(mt.currentIndex())
    assert bars[1].property("active") is True and bars[0].property("active") is False   # hàng 1 bị làm nhạt
    mt.setCurrentIndex(0)
    assert bars[0].property("active") is True and bars[1].property("active") is False
    assert bars[0].currentIndex() == 0
    assert "Trộn đề" in mt.tabText(0)


def test_import_type_counts_and_fast_unaccent(win, app, tmp_path):
    """Sau mỗi lệnh nhập có số câu theo loại (TN, ĐS, TLN, TL); unaccent nhanh và đúng."""
    from nganhangde.typecount import fmt, count_types
    from nganhangde.textnorm import unaccent
    from nganhangde.mylt_import import import_rows
    from nganhangde.db import Bank
    import unicodedata
    s = "Phương trình ậ ồ Đ đ ₂ ß"
    exp = "".join(c for c in unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D")) if unicodedata.category(c) != "Mn")
    assert unaccent(s) == exp and unaccent("abc") == "abc"
    qs = parse_file(SAMPLE)
    assert "TN:" in fmt(count_types(qs)) and "ĐS:" in fmt({}) and "TLN:" in fmt({"KQ": 2})
    b = Bank(str(tmp_path / "k.db"))
    rows = [{"NoiDung": q.raw, "IDCauHoi": "", "TuLuan": "0", "SoLan": "0"} for q in qs]
    res = import_rows(b, rows, source="t")
    assert sum(res["by_type"].values()) == res["them"] > 0
    assert "TN" in res["by_type"]
    assert fmt({"TN": 1, "KQ": 2}).startswith("TN: 1 · ĐS: 0 · TLN: 2 · TL: 0")


def test_review_advanced_checks(win, app, tmp_path, monkeypatch):
    """Rà soát nâng cao: AI giải & so đáp án, bổ sung lời giải thiếu, xoá câu trùng (file), phương án trùng."""
    from PySide6.QtWidgets import QMessageBox
    from nganhangde.ui.dialogs import ai_settings
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    from PySide6.QtWidgets import QFileDialog
    out_path = str(tmp_path / "de_dasoat.tex")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (out_path, "")))

    class FakeClient:
        def generate_json(self, prompt, schema=None):
            return {"dap_an": "A", "loi_giai": "Giải: đáp án là A.", "ghi_chu": ""}
    monkeypatch.setattr(ai_settings, "ensure_client", lambda w: FakeClient())
    # file có câu trùng + câu không có lời giải
    t = open(SAMPLE, encoding="utf-8").read()
    f = tmp_path / "de.tex"
    f.write_text(t + "\n" + t, encoding="utf-8")
    rp = win.review_panel
    rp.cb_src.setCurrentIndex(rp.cb_src.findData("file"))
    rp.e_file.setText(str(f))
    rp.run()
    n_before = len(parse_file(str(f)))
    rp.ai_check()
    assert all("ai" in it for it in rp.items) and rp.items
    rp.dedupe()
    left = parse_file(out_path)                        # file gốc giữ nguyên, kết quả ghi ra file mới
    assert len(left) < n_before and len({q.fingerprint for q in left}) == len(left)   # còn đúng 1 câu mỗi nhóm
    assert len(parse_file(str(f))) == n_before          # file gốc không bị sửa
    rp.run()
    rp.check_dup_choices()


def test_export_has_extest_and_standalone_vietnamese(tmp_path):
    """Đề xuất luôn có ex_test.sty cạnh file .tex; mẫu hình có gói tiếng Việt cho pdflatex và xelatex/lualatex."""
    import random
    from nganhangde.exporter import ExportOptions, export_versions
    from nganhangde.generator import MixOptions, mix_versions, sections_from_questions
    from nganhangde.ui.tabs.draw_studio import STANDALONE
    vs = mix_versions(sections_from_questions(parse_file(SAMPLE)), ["101"], random.Random(1), MixOptions())
    export_versions(vs, str(tmp_path / "out"), options=ExportOptions())
    assert os.path.isfile(str(tmp_path / "out" / "ex_test.sty"))
    assert "iftex" in STANDALONE and "vietnam" in STANDALONE and "fontspec" in STANDALONE


def test_manim_dialog_steps_guarded(win, app):
    """Hộp thoại Bài giảng Manim dựng được; các bước chưa đủ dữ liệu báo đúng, không lỗi."""
    from nganhangde.ui.dialogs.manim_lecture import ManimLectureDialog
    d = ManimLectureDialog(win)
    d.step2()
    assert "Chưa có bản thiết kế" in d.log.toPlainText()
    d.step5()
    assert "Chưa có video" in d.log.toPlainText()
    d.step6()
    assert "Chưa có video" in d.log.toPlainText()
    assert d.cb_q.count() == 3


def test_manim_step1_runs_worker(win, app, tmp_path, monkeypatch):
    """Bước ① (AI thiết kế) chạy được trong luồng nền; không lỗi tham số job."""
    from nganhangde.ui.dialogs import ai_settings
    from nganhangde.ui.dialogs.manim_lecture import ManimLectureDialog

    class FakeClient:
        def generate_json(self, prompt, schema=None):
            return {"title": "Hàm số", "scenes": [{"title": "Định nghĩa", "blocks": [
                {"kind": "text", "content": "Hàm số bậc hai"}]}]}
    monkeypatch.setattr(ai_settings, "ensure_client", lambda w: FakeClient())
    src = tmp_path / "nguon.tex"
    src.write_text("Hàm số bậc hai $y=ax^2$", encoding="utf-8")
    d = ManimLectureDialog(win, str(src))
    d.step1()
    text = d.log.toPlainText()
    assert "AI lỗi" not in text and "1 cảnh" in text
    assert d.design and d.design["scenes"][0]["title"] == "Định nghĩa"

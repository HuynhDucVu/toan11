"""Lớp tương thích: giao diện đã được tách sang gói nganhangde/ui/.

Giữ lại để `from nganhangde.gui_qt import run` và các tên cũ (MainWindow, ResultDialog…) vẫn dùng được.
"""
from .ui.common import APP_NAME, MAU_CAU, STYLE, TEN_LOAI, TEN_MUC
from .ui.app import run
from .ui.dialogs.ai_settings import GeminiSettingsDialog
from .ui.dialogs.assign_id import AssignIdDialog, IdPicker
from .ui.dialogs.edit import EditDialog
from .ui.dialogs.idmap import IdMapDialog
from .ui.dialogs.pdf import PdfResultDialog, PdfSettingsDialog, prepare_tex_for_pdf
from .ui.dialogs.result import ResultDialog, versions_report_html
from .ui.dialogs.swap import SwapDialog
from .ui.dialogs.update import UpdateDialog
from .ui.main_window import MainWindow
from .ui.tabs.draw import DrawPanel, PlotView
from .ui.tabs.exam_options import ExamOptionsBox, MixOptionsBox
from .ui.tabs.generator import GeneratorPanel
from .ui.tabs.make_question import MakeQuestionPanel
from .ui.tabs.review import ReviewPanel
from .ui.tabs.stats import StatsPanel
from .ui.tabs.tools import ToolsPanel
from .ui.workers import AiWorker, BuildWorker, UpdateWorker
from .ui.common import LatexHighlighter, latex_editor, resource_dir, scroll_of

__all__ = ['APP_NAME', 'AiWorker', 'AssignIdDialog', 'BuildWorker', 'DrawPanel', 'EditDialog', 'ExamOptionsBox',
           'GeminiSettingsDialog', 'GeneratorPanel', 'IdMapDialog', 'IdPicker', 'LatexHighlighter', 'MAU_CAU',
           'MainWindow', 'MakeQuestionPanel', 'MixOptionsBox', 'PdfResultDialog', 'PdfSettingsDialog', 'PlotView',
           'ResultDialog', 'ReviewPanel', 'STYLE', 'StatsPanel', 'SwapDialog', 'TEN_LOAI', 'TEN_MUC', 'ToolsPanel',
           'UpdateDialog', 'UpdateWorker', 'latex_editor', 'prepare_tex_for_pdf', 'resource_dir', 'run',
           'scroll_of', 'versions_report_html']

if __name__ == "__main__":
    import sys
    sys.exit(run())

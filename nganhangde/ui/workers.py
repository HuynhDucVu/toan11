"""Các luồng nền (QThread): gọi Gemini, kiểm tra/tải cập nhật, biên dịch PDF."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class AiWorker(QThread):
    progress = Signal(int, int)

    def __init__(self, client, questions, mapping, scope, default_level, judge_level, batch):
        super().__init__()
        self.args = (client, questions, mapping, scope, default_level, judge_level, batch)
        self.results, self.error = [], ""

    def run(self):
        from .. import aiid
        client, qs, mapping, scope, lv, judge, batch = self.args
        try:
            self.results = aiid.classify(client, qs, mapping, scope=scope, default_level=lv, judge_level=judge,
                                         batch=batch, progress=lambda i, n: self.progress.emit(i, n),
                                         should_stop=self.isInterruptionRequested)
        except aiid.AIError as e:
            self.error = str(e)
        except Exception as e:  # noqa: BLE001
            self.error = f"Lỗi khi gọi Gemini: {e}"


class UpdateWorker(QThread):
    """Kiểm tra bản mới (mode='check') hoặc tải exe (mode='download') ở luồng nền."""
    progress = Signal(int, int)

    def __init__(self, mode, rel=None):
        super().__init__()
        self.mode, self.rel, self.result, self.error = mode, rel, None, ""

    def run(self):
        from .. import updater
        try:
            if self.mode == "check":
                self.result = updater.latest_release()
            else:
                self.result = updater.download(self.rel, progress=lambda d, t: self.progress.emit(d, t),
                                               should_stop=self.isInterruptionRequested)
        except updater.UpdateError as e:
            self.error = str(e)
        except Exception as e:  # noqa: BLE001
            self.error = f"Lỗi cập nhật: {e}"


class BuildWorker(QThread):
    """Biên dịch PDF ở luồng nền."""
    progress = Signal(int, int, str)
    done = Signal(list)

    def __init__(self, paths, engine, opts):
        super().__init__()
        self.paths, self.eng, self.o = list(paths), engine, opts

    def run(self):
        from ..pdfbuild import compile_tex
        out = []
        for i, p in enumerate(self.paths, 1):
            if self.isInterruptionRequested():
                break
            self.progress.emit(i, len(self.paths), p)
            try:
                out.append(compile_tex(p, self.eng, runs=self.o["runs"], extest_dir=self.o["extest_dir"],
                                       clean=self.o["clean"]))
            except Exception as e:  # noqa: BLE001
                from ..pdfbuild import BuildResult
                out.append(BuildResult(p, False, errors=[str(e)]))
        self.done.emit(out)


class TaskWorker(QThread):
    """Chạy một hàm bất kì ở luồng nền. Hàm nhận progress=, should_stop= nếu `with_progress`."""
    progress = Signal(int, int)

    def __init__(self, fn, *args, with_progress=False, **kw):
        super().__init__()
        self.fn, self.args, self.kw, self.with_progress = fn, args, kw, with_progress
        self.result, self.error = None, ""

    def run(self):
        from ..aiid import AIError
        kw = dict(self.kw)
        if self.with_progress:
            kw.update(progress=lambda i, n: self.progress.emit(i, n), should_stop=self.isInterruptionRequested)
        try:
            self.result = self.fn(*self.args, **kw)
        except AIError as e:
            self.error = str(e)
        except Exception as e:  # noqa: BLE001
            self.error = f"{type(e).__name__}: {e}"

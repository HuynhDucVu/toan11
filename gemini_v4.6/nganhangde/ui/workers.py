import traceback
from typing import Any, Callable
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class AsyncTaskWorker(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.finished.emit(self.fn(*self.args, **self.kwargs))
        except Exception:
            self.signals.error.emit(traceback.format_exc())


def run_in_background(fn: Callable[..., Any], *args: Any, on_finished=None, on_error=None, **kwargs: Any) -> AsyncTaskWorker:
    w = AsyncTaskWorker(fn, *args, **kwargs)
    if on_finished:
        w.signals.finished.connect(on_finished)
    if on_error:
        w.signals.error.connect(on_error)
    QThreadPool.globalInstance().start(w)
    return w

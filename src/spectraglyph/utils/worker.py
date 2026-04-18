from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class Worker(QRunnable):
    """Runs ``fn`` in the thread pool; results are emitted via ``signals``.

    Pass ``parent`` (usually the main window) so ``_WorkerSignals`` survives after the
    pool deletes this runnable: ``QueuedConnection`` delivers to the GUI thread only
    after ``run()`` returns—without a parent, the signals object can be destroyed first
    and slots never run. Use ``QueuedConnection`` so GUI slots run on the main thread.
    """

    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        parent: QObject | None = kwargs.pop("parent", None)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _WorkerSignals(parent)

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.signals.finished.emit(result)


def pool() -> QThreadPool:
    return QThreadPool.globalInstance()

from PyQt6.QtCore import QThread, QObject, pyqtSignal
import traceback


class WorkerSignals(QObject):
    progress = pyqtSignal(object, int, str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(object, str)


class WorkerThread(QThread):
    def __init__(self, worker_id, queue_manager, project_runners, parent=None):
        super().__init__(parent)
        self.worker_id = worker_id
        self.queue = queue_manager
        self.runners = project_runners
        self.signals = WorkerSignals()
        self._running = True

    def run(self):
        while self._running:
            task = self.queue.get_next_task()
            if task is None:
                self.msleep(1000)
                continue

            runner = self.runners.get(task.type.value)
            if runner is None:
                self.queue.mark_failed(task, f"No runner for task type: {task.type}")
                continue

            def progress_cb(pct, step=""):
                self.queue.update_progress(task, pct, step)
                self.signals.progress.emit(task, pct, step)

            try:
                result = runner(task, progress_cb)
                self.queue.mark_completed(task)
                self.signals.finished.emit(task)
            except Exception as e:
                tb = traceback.format_exc()
                self.queue.mark_failed(task, f"{e}\n{tb}")
                self.signals.failed.emit(task, str(e))

    def stop(self):
        self._running = False


class WorkerPool(QObject):
    def __init__(self, queue_manager, project_runners, worker_count=2, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.runners = project_runners
        self.workers = []

        for i in range(worker_count):
            worker = WorkerThread(i, queue_manager, project_runners, parent)
            self.workers.append(worker)

    def start_all(self):
        for w in self.workers:
            w.start()

    def stop_all(self):
        for w in self.workers:
            w.stop()
        for w in self.workers:
            w.wait(5000)

    def set_worker_count(self, count):
        self.stop_all()
        count = max(1, min(4, count))
        self.workers = []
        for i in range(count):
            worker = WorkerThread(i, self.queue, self.runners)
            self.workers.append(worker)
        self.start_all()

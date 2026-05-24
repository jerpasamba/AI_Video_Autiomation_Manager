from PyQt6.QtCore import QThread, QObject, pyqtSignal
import traceback

from app.queue_manager import TaskType


class PipelineWorkerSignals(QObject):
    progress = pyqtSignal(object, int, str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(object, str)


class PipelineWorker(QThread):
    def __init__(self, name, task_type, queue_manager, runners, parent=None):
        super().__init__(parent)
        self.name = name
        self.task_type = task_type
        self.queue = queue_manager
        self.runners = runners
        self.signals = PipelineWorkerSignals()
        self._running = True

    def run(self):
        while self._running:
            task = self.queue.get_next_task(self.task_type)
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
                runner(task, progress_cb)
                self.queue.mark_completed(task)
                self.signals.finished.emit(task)
            except Exception as e:
                tb = traceback.format_exc()
                self.queue.mark_failed(task, f"{e}\n{tb}")
                self.signals.failed.emit(task, str(e))

    def stop(self):
        self._running = False


class WorkerPool(QObject):
    def __init__(self, queue_manager, project_runners, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.runners = project_runners
        self.workers = []

        self.workers.append(PipelineWorker(
            "manhwa", TaskType.MANHWA_CHAPTER, queue_manager, project_runners, parent
        ))
        self.workers.append(PipelineWorker(
            "anime", TaskType.ANIME_SHORT, queue_manager, project_runners, parent
        ))
        self.workers.append(PipelineWorker(
            "minecraft", TaskType.MINECRAFT_STORY, queue_manager, project_runners, parent
        ))
        self.workers.append(PipelineWorker(
            "upload", TaskType.UPLOAD_VIDEO, queue_manager, project_runners, parent
        ))

    def start_all(self):
        for w in self.workers:
            w.start()

    def stop_all(self):
        for w in self.workers:
            w.stop()
        for w in self.workers:
            w.wait(5000)

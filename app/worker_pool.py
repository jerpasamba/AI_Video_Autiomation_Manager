from PyQt6.QtCore import QThread, QObject, pyqtSignal
import traceback

from app.queue_manager import TaskType


class PipelineWorkerSignals(QObject):
    progress = pyqtSignal(object, int, str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(object, str)


class PipelineWorker(QThread):
    def __init__(self, name, task_type, queue_manager, runners, parent=None, task_filter=None):
        super().__init__(parent)
        self.name = name
        self.task_type = task_type
        self.queue = queue_manager
        self.runners = runners
        self.signals = PipelineWorkerSignals()
        self._running = True
        self.task_filter = task_filter

    def run(self):
        while self._running:
            task = self.queue.get_next_task(self.task_type, predicate=self.task_filter)
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
                if task.cancelled:
                    self.queue.mark_failed(task, "Task was cancelled before execution")
                    continue
                runner(task, progress_cb)
                if task.cancelled:
                    self.queue.mark_failed(task, "Task was cancelled during execution")
                else:
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
            "movie_reel", TaskType.MOVIE_REEL, queue_manager, project_runners, parent
        ))
        # Uploads can block (e.g. YouTube OAuth waiting for user in browser).
        # Split workers by platform so YouTube auth doesn't stall Facebook uploads.
        cfg = getattr(queue_manager, "config", {}) or {}

        def _plat(p):
            if p == "youtube":
                return lambda t: (t.params or {}).get("platform", "youtube") in ("youtube", "youtube_short")
            return lambda t: (t.params or {}).get("platform", "youtube") == p

        yt_workers = cfg.get("youtube_upload_workers", 1)
        fb_workers = cfg.get("facebook_upload_workers", 1)
        tt_workers = cfg.get("tiktok_upload_workers", 1)
        try:
            yt_workers = int(yt_workers)
        except Exception:
            yt_workers = 1
        try:
            fb_workers = int(fb_workers)
        except Exception:
            fb_workers = 1
        try:
            tt_workers = int(tt_workers)
        except Exception:
            tt_workers = 1
        yt_workers = max(1, min(4, yt_workers))
        fb_workers = max(1, min(4, fb_workers))
        tt_workers = max(1, min(4, tt_workers))

        for i in range(fb_workers):
            self.workers.append(PipelineWorker(
                f"upload-facebook-{i+1}",
                TaskType.UPLOAD_VIDEO,
                queue_manager,
                project_runners,
                parent,
                task_filter=_plat("facebook"),
            ))

        for i in range(yt_workers):
            self.workers.append(PipelineWorker(
                f"upload-youtube-{i+1}",
                TaskType.UPLOAD_VIDEO,
                queue_manager,
                project_runners,
                parent,
                task_filter=_plat("youtube"),
            ))

        for i in range(tt_workers):
            self.workers.append(PipelineWorker(
                f"upload-tiktok-{i+1}",
                TaskType.UPLOAD_VIDEO,
                queue_manager,
                project_runners,
                parent,
                task_filter=_plat("tiktok"),
            ))

    def start_all(self):
        for w in self.workers:
            w.start()

    def stop_all(self):
        for w in self.workers:
            w.stop()
        for w in self.workers:
            w.wait(5000)

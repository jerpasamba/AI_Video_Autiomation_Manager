import json
import uuid
import threading
import os
from datetime import datetime
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    MANHWA_CHAPTER = "manhwa_chapter"
    ANIME_SHORT = "anime_short"
    MINECRAFT_STORY = "minecraft_story"
    UPLOAD_VIDEO = "upload_video"


class Task:
    def __init__(self, task_type, params=None, title=None):
        self.id = str(uuid.uuid4())[:8]
        self.type = task_type
        self.params = params or {}
        self.title = title or task_type.value
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.step_name = ""
        self.created_at = datetime.now().isoformat()
        self.started_at = None
        self.completed_at = None
        self.error = None
        self.cancelled = False

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type.value,
            "params": self.params,
            "title": self.title,
            "status": self.status.value,
            "progress": self.progress,
            "step_name": self.step_name,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data):
        t = cls(TaskType(data["type"]), data.get("params", {}), data.get("title"))
        t.id = data["id"]
        t.status = TaskStatus(data["status"])
        t.progress = data.get("progress", 0)
        t.step_name = data.get("step_name", "")
        t.created_at = data.get("created_at", t.created_at)
        t.started_at = data.get("started_at")
        t.completed_at = data.get("completed_at")
        t.error = data.get("error")
        return t


class QueueManager(QObject):
    progress_signal = pyqtSignal(str, int, str)
    status_signal = pyqtSignal(str, str)
    queue_changed = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.monitor = None
        self.auto_refill_callback = None
        self._tasks = []
        self._lock = threading.Lock()
        self._paused = False
        self._queue_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "queue.json",
        )
        self._load()

    def set_monitor(self, monitor):
        self.monitor = monitor

    @property
    def paused(self):
        return self._paused

    def pause(self):
        self._paused = True
        self.queue_changed.emit()

    def resume(self):
        self._paused = False
        self.queue_changed.emit()

    def add_task(self, task_type, params=None, title=None):
        task = Task(task_type, params, title)
        with self._lock:
            self._tasks.append(task)
            self._save()
        self.queue_changed.emit()
        return task

    def cancel_task(self, task_id):
        with self._lock:
            for t in self._tasks:
                if t.id == task_id and t.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    if t.status == TaskStatus.RUNNING:
                        t.cancelled = True
                    t.status = TaskStatus.CANCELLED
                    t.completed_at = datetime.now().isoformat()
                    self._save()
                    self.status_signal.emit(t.id, TaskStatus.CANCELLED.value)
        self.queue_changed.emit()

    def clear_completed(self):
        with self._lock:
            self._tasks = [t for t in self._tasks if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
            self._save()
        self.queue_changed.emit()

    def get_next_task(self):
        if self._paused:
            return None
        with self._lock:
            for t in self._tasks:
                if t.status == TaskStatus.PENDING and not t.cancelled:
                    t.status = TaskStatus.RUNNING
                    t.started_at = datetime.now().isoformat()
                    self._save()
                    self.status_signal.emit(t.id, TaskStatus.RUNNING.value)
                    return t
        return None

    def mark_completed(self, task):
        with self._lock:
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.completed_at = datetime.now().isoformat()
            self._save()
        self.status_signal.emit(task.id, TaskStatus.COMPLETED.value)
        self.queue_changed.emit()
        if self.monitor:
            if task.type == TaskType.MANHWA_CHAPTER:
                self.monitor.increment_generated("manhwa")
            elif task.type == TaskType.ANIME_SHORT:
                self.monitor.increment_generated("anime")
            elif task.type == TaskType.MINECRAFT_STORY:
                self.monitor.increment_generated("minecraft")
            elif task.type == TaskType.UPLOAD_VIDEO:
                platform = task.params.get("platform", "facebook")
                self.monitor.increment_uploaded(platform, success=True)
        if task.type != TaskType.UPLOAD_VIDEO and self.auto_refill_callback:
            self.auto_refill_callback(task)

    def mark_failed(self, task, error):
        with self._lock:
            task.status = TaskStatus.FAILED
            task.error = str(error)
            task.completed_at = datetime.now().isoformat()
            self._save()
        self.status_signal.emit(task.id, TaskStatus.FAILED.value)
        self.queue_changed.emit()
        if self.monitor:
            if task.type == TaskType.MANHWA_CHAPTER:
                self.monitor.increment_failed_generation("manhwa")
            elif task.type == TaskType.ANIME_SHORT:
                self.monitor.increment_failed_generation("anime")
            elif task.type == TaskType.MINECRAFT_STORY:
                self.monitor.increment_failed_generation("minecraft")
            elif task.type == TaskType.UPLOAD_VIDEO:
                platform = task.params.get("platform", "facebook")
                self.monitor.increment_uploaded(platform, success=False)

    def update_progress(self, task, progress, step_name=""):
        with self._lock:
            task.progress = progress
            if step_name:
                task.step_name = step_name
        self.progress_signal.emit(task.id, progress, step_name)

    def get_tasks(self, status_filter=None):
        with self._lock:
            if status_filter:
                return [t for t in self._tasks if t.status in status_filter]
            return list(self._tasks)

    def get_running_count(self):
        with self._lock:
            return sum(1 for t in self._tasks if t.status == TaskStatus.RUNNING)

    def get_pending_count(self):
        with self._lock:
            return sum(1 for t in self._tasks if t.status == TaskStatus.PENDING)

    def get_completed_count(self):
        with self._lock:
            return sum(1 for t in self._tasks if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED))

    def _save(self):
        try:
            data = [t.to_dict() for t in self._tasks]
            with open(self._queue_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load(self):
        try:
            if os.path.exists(self._queue_path):
                with open(self._queue_path) as f:
                    data = json.load(f)
                    self._tasks = [Task.from_dict(d) for d in data]
        except Exception:
            self._tasks = []

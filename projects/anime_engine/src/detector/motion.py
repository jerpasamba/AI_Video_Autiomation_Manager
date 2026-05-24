import re
from src.utils.ffmpeg import ffmpeg_cmd, ffprobe_cmd


class MotionAnalyzer:
    def __init__(self, threshold=0.4):
        self.threshold = threshold

    def analyze(self, video_path, progress_callback=None):
        if progress_callback:
            progress_callback("  Analyzing with ffmpeg...")

        try:
            duration = self._get_duration(video_path)
            if duration <= 0:
                return [], [], 0, 0
        except Exception as e:
            if progress_callback:
                progress_callback(f"  Cannot read video: {e}")
            return [], [], 0, 0

        if progress_callback:
            progress_callback(f"  Video duration: {duration:.0f}s")

        scene_changes = self._detect_scenes(video_path)
        self.last_scene_changes = scene_changes
        if progress_callback:
            progress_callback(f"  Found {len(scene_changes)} scene cuts")

        if duration <= 0:
            return [], [], 30, 0

        window_size = max(5, int(duration / 30))
        step = max(2, window_size // 2)
        motion_scores = []
        timestamps = []

        for t_start in [s * step for s in range(int(duration / step))]:
            t_end = min(t_start + window_size, duration)
            cuts = sum(1 for c in scene_changes if t_start <= c < t_end)
            freq = cuts / max(t_end - t_start, 1)
            score = min(freq / 2.0, 1.0)
            motion_scores.append(score)
            timestamps.append((t_start + t_end) / 2)

        if progress_callback and motion_scores:
            max_s = max(motion_scores)
            if max_s > 0.2:
                action_regions = sum(1 for s in motion_scores if s > 0.3)
                pct = int(action_regions / len(motion_scores) * 100)
                progress_callback(f"  Action estimate: {pct}% of video has high activity")

        return motion_scores, timestamps, 30.0, float(duration)

    def _get_duration(self, video_path):
        result = ffprobe_cmd([
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ], capture_output=True, text=True)
        if result.returncode != 0:
            return 0
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 0

    def _detect_scenes(self, video_path):
        result = ffmpeg_cmd([
            "-i", video_path,
            "-filter:v", f"select='gt(scene,{self.threshold})',showinfo",
            "-f", "null",
            "-"
        ], capture_output=True, text=True)
        output = result.stderr

        timestamps = []
        for line in output.split("\n"):
            m = re.search(r"pts_time:([\d.]+)", line)
            if m:
                timestamps.append(float(m.group(1)))

        return timestamps

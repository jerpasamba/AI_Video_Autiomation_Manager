import re
from src.utils.ffmpeg import ffmpeg_cmd, ffprobe_cmd


class AudioEnergyDetector:
    def __init__(self, energy_threshold=0.5):
        self.energy_threshold = energy_threshold

    def analyze(self, video_path, max_duration=600):
        try:
            duration = self._get_duration(video_path)
            if duration <= 0:
                return [], [], 0
        except Exception:
            return [], [], 0

        ffmpeg_cmd([
            "-i", video_path,
            "-t", str(min(duration, max_duration)),
            "-af", "volumedetect", "-f", "null", "-"
        ], capture_output=True, text=True)

        result2 = ffmpeg_cmd([
            "-i", video_path,
            "-t", str(min(duration, max_duration)),
            "-af", "astats=measure_perchannel=1:metadata=1:reset=1",
            "-f", "null", "-"
        ], capture_output=True, text=True)

        rms_values = []
        timestamps = []
        interval = 0.5
        current_time = 0.0

        for line in result2.stderr.split("\n"):
            if "Overall RMS level" in line or "RMS level" in line:
                m = re.search(r"RMS level: ([\-\d.]+) dB", line)
                if m:
                    db_value = float(m.group(1))
                    linear = max(0, min(1, (db_value + 60) / 60))
                    rms_values.append(linear)
                    timestamps.append(current_time)
                    current_time += interval

        if not rms_values:
            return [], [], 0

        max_rms = max(rms_values)
        if max_rms > 0:
            rms_values = [r / max_rms for r in rms_values]

        return rms_values, timestamps, 44100

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

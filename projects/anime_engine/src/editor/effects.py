import subprocess
import random


HIGHLIGHT_PHRASES = [
    "🔥 EPIC!",
    "⚡ INCREDIBLE!",
    "💥 AMAZING!",
    "🎯 PERFECT!",
    "💪 LEGENDARY!",
    "🔥 FIRE!",
    "👑 GOD TIER!",
    "⚡ UNREAL!",
]


class EffectsOverlay:
    def __init__(self, banner_duration=2.0):
        self.banner_duration = banner_duration
        self.phrases = HIGHLIGHT_PHRASES

    def add_highlight_banner(self, video_path, output_path, timestamp=None, text=None):
        phrase = text or random.choice(self.phrases)

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf",
            f"drawtext=text='{self._esc(phrase)}':fontcolor=yellow:fontsize=72:"
            f"x=(w-text_w)/2:y=h*0.15:enable='between(t,0,{self.banner_duration})':"
            f"borderw=2:bordercolor=black",
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_path
        ]

        if timestamp is not None:
            cmd.insert(cmd.index("-i") + 2, "-ss")
            cmd.insert(cmd.index("-ss") + 1, str(timestamp))

        subprocess.run(cmd, check=True, capture_output=True, text=True)

        return output_path

    def _esc(self, text):
        return text.replace("'", "'\\''").replace(":", "\\:")

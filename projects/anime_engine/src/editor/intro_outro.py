from src.utils.ffmpeg import ffmpeg_cmd


class IntroOutroGenerator:
    def __init__(self, intro_text="Anime Highlights", outro_text="Subscribe for more!"):
        self.intro_text = intro_text
        self.outro_text = outro_text

    def generate_intro(self, output_path, duration=3, size=(1080, 1920), intro_text=None):
        if intro_text is None:
            intro_text = self.intro_text
        ffmpeg_cmd([
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=#141428:s={size[0]}x{size[1]}:d={duration}",
            "-vf",
            f"drawtext=text='{self._esc(intro_text)}':fontcolor=white:fontsize=72:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-30,"
            f"drawtext=text='{self._esc('Anime Shorts')}':fontcolor=yellow:fontsize=36:"
            f"x=(w-text_w)/2:y=(h+text_h)/2+30",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            output_path
        ], check=True, capture_output=True, text=True)
        return output_path

    def generate_outro(self, output_path, duration=3, size=(1080, 1920)):
        ffmpeg_cmd([
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=#141428:s={size[0]}x{size[1]}:d={duration}",
            "-vf",
            f"drawtext=text='{self._esc(self.outro_text)}':fontcolor=white:fontsize=64:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-30,"
            f"drawtext=text='{self._esc('Like & Subscribe!')}':fontcolor=gray:fontsize=32:"
            f"x=(w-text_w)/2:y=(h+text_h)/2+30",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            output_path
        ], check=True, capture_output=True, text=True)
        return output_path

    @staticmethod
    def _esc(text):
        return text.replace("'", "'\\''").replace(":", "\\:")

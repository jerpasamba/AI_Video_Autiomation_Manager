import os
import json


class CaptionGenerator:
    def __init__(self, font_size=36, position="bottom"):
        self.font_size = font_size
        self.position = position

    def transcribe(self, video_path, model_name="base"):
        import whisper
        model = whisper.load_model(model_name)
        result = model.transcribe(video_path, language=None)

        return result["segments"]

    def add_captions_to_video(self, video_path, segments, output_path):
        from moviepy import VideoFileClip, TextClip, CompositeVideoClip

        clip = VideoFileClip(video_path)

        txt_clips = []
        for seg in segments:
            duration = seg["end"] - seg["start"]
            if duration < 0.3:
                continue

            txt = TextClip(
                text=seg["text"].strip(),
                font_size=self.font_size,
                color="white",
                font="Arial",
                stroke_color="black",
                stroke_width=2,
                text_align="center",
                method="caption",
                size=(clip.w - 100, None)
            )

            if self.position == "top":
                txt = txt.with_position(("center", 50))
            else:
                txt = txt.with_position(("center", clip.h - 150))

            txt = txt.with_start(seg["start"]).with_duration(duration)
            txt_clips.append(txt)

        final = CompositeVideoClip([clip, *txt_clips])
        final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        clip.close()
        final.close()

        return output_path

    def format_as_srt(self, segments):
        lines = []
        for i, seg in enumerate(segments, 1):
            start = self._seconds_to_srt_time(seg["start"])
            end = self._seconds_to_srt_time(seg["end"])
            lines.append(str(i))
            lines.append(f"{start} --> {end}")
            lines.append(seg["text"].strip())
            lines.append("")
        return "\n".join(lines)

    def _seconds_to_srt_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

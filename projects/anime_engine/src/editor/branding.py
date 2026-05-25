import os
import re
from src.utils.ffmpeg import ffmpeg_cmd


class BrandingOverlay:
    def __init__(self, logo_path="assets/logo.png", channel_name="Anime Shorts",
                 channel_handle="@animeshorts"):
        self.logo_path = logo_path
        self.channel_name = channel_name
        self.channel_handle = channel_handle

    def add_branding(self, video_path, output_path, anime_title="Anime Highlight",
                     clip_index=1, total_clips=1):
        logo_exists = os.path.exists(self.logo_path)
        safe_title = re.sub(r'[^a-zA-Z0-9\s\-]', '', anime_title)[:40].strip()
        safe_channel = re.sub(r'[^a-zA-Z0-9\s]', '', self.channel_name)[:25].strip()
        safe_handle = re.sub(r'[^a-zA-Z0-9_@]', '', self.channel_handle)[:25].strip()
        font = "fontfile='C\\:/Windows/Fonts/arial.ttf'"

        logo_input = []
        if logo_exists:
            logopath = video_path.replace(".mp4", "_logo.png")
            ffmpeg_cmd(["-y", "-i", self.logo_path, "-vf", "scale=-1:130", logopath],
                       check=True, capture_output=True)
            logo_input = ["-i", logopath]

        # Video: scale to fit 1080 width, place at y=640 (just below header)
        vid_scale = "scale=1080:-1:force_original_aspect_ratio=decrease"

        if logo_exists:
            f = (
                f"color=c=#0d0d1a:s=1080x1920:r=30,format=yuv420p[bg];"
                f"[0:v]{vid_scale}[vs];"
                f"[bg][vs]overlay=(W-w)/2:680:shortest=1[base];"
                f"[base][1:v]overlay=(W)/2-65:410[base2];"
                f"[base2]drawtext=text='{safe_channel}':fontcolor=white:fontsize=34:"
                f"x=(w-text_w)/2:y=555:{font},"
                f"drawtext=text='{safe_handle}':fontcolor=#FFD700:fontsize=22:"
                f"x=(w-text_w)/2:y=600:{font},"
                f"drawtext=text='{safe_title}':fontcolor=white:fontsize=34:"
                f"x=(w-text_w)/2:y=635:box=1:boxcolor=black@0.4:boxborderw=8:{font}[out]"
            )
        else:
            f = (
                f"color=c=#0d0d1a:s=1080x1920:r=30,format=yuv420p[bg];"
                f"[0:v]{vid_scale}[vs];"
                f"[bg][vs]overlay=(W-w)/2:680:shortest=1[base];"
                f"[base]drawtext=text='{safe_channel}':fontcolor=white:fontsize=34:"
                f"x=(w-text_w)/2:y=555:{font},"
                f"drawtext=text='{safe_handle}':fontcolor=#FFD700:fontsize=22:"
                f"x=(w-text_w)/2:y=600:{font},"
                f"drawtext=text='{safe_title}':fontcolor=white:fontsize=34:"
                f"x=(w-text_w)/2:y=635:box=1:boxcolor=black@0.4:boxborderw=8:{font}[out]"
            )

        cmd = [
            "-y", "-i", video_path,
            *logo_input,
            "-filter_complex", f,
            "-map", "[out]",
            "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-movflags", "+faststart",
            output_path
        ]

        ffmpeg_cmd(cmd, check=True, capture_output=True, text=True)

        if logo_exists:
            lp = video_path.replace(".mp4", "_logo.png")
            if os.path.exists(lp):
                os.unlink(lp)

        return output_path

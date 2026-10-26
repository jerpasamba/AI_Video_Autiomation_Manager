import os
import re
from src.utils.ffmpeg import ffmpeg_cmd


class BrandingOverlay:
    def __init__(self, logo_path="assets/logo.png", channel_name="ZeroBalanceManhwa",
                 channel_handle="@ZeroBalanceManhwa"):
        self.logo_path = logo_path
        self.channel_name = channel_name
        self.channel_handle = channel_handle

    def add_branding(self, video_path, output_path, anime_title="Anime Highlight",
                     clip_index=1, total_clips=1):
        logo_exists = os.path.exists(self.logo_path)

        # Clean title text formatting with proper spacing
        clean_title = anime_title.replace("_", " ").replace("-", " ")
        clean_title = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean_title)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        safe_title = re.sub(r'[^a-zA-Z0-9\s\-\:]', '', clean_title)[:42].strip()

        safe_channel = re.sub(r'[^a-zA-Z0-9\s]', '', self.channel_name)[:25].strip()
        safe_handle = re.sub(r'[^a-zA-Z0-9_@]', '', self.channel_handle)[:25].strip()

        font_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        font_local = os.path.join(font_dir, "arial.ttf")
        if not os.path.exists(font_local):
            winfont = r"C:\Windows\Fonts\arial.ttf"
            if os.path.exists(winfont):
                import shutil
                shutil.copy2(winfont, font_local)
        root = os.path.dirname(os.path.dirname(font_dir))  # project root
        font = f"fontfile={os.path.relpath(font_local, root).replace(chr(92), '/')}"

        logo_input = []
        if logo_exists:
            logopath = video_path.replace(".mp4", "_logo.png")
            try:
                ffmpeg_cmd(["-y", "-i", self.logo_path, "-vf", "scale=-1:110", logopath],
                           check=True, capture_output=True)
                logo_input = ["-i", logopath]
            except Exception:
                logo_exists = False

        # Dynamic blurred background filter
        # 1. Fill entire 1080x1920 portrait with blurred video
        # 2. Scale crisp main video to 1080 width and center vertically (overlay at (W-w)/2:(H-h)/2)
        # 3. Add stylish top branding and title
        # 4. Add stylish bottom call to action
        bg_filter = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,boxblur=25:5,eq=brightness=-0.22:saturation=1.25[bg];"
            "[0:v]scale=1080:-1:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
        )

        if logo_exists:
            f = (
                f"{bg_filter};"
                f"[base][1:v]overlay=(W-w)/2:390[base2];"
                f"[base2]drawtext=text='{safe_channel}':fontcolor=white:fontsize=32:"
                f"x=(w-text_w)/2:y=515:{font},"
                f"drawtext=text='{safe_handle}':fontcolor=#FFD700:fontsize=22:"
                f"x=(w-text_w)/2:y=555:{font},"
                f"drawtext=text='{safe_title}':fontcolor=white:fontsize=30:"
                f"x=(w-text_w)/2:y=595:box=1:boxcolor=black@0.55:boxborderw=10:{font},"
                f"drawtext=text='FOLLOW FOR MORE':fontcolor=#FFD700:fontsize=24:"
                f"x=(w-text_w)/2:y=1340:box=1:boxcolor=black@0.55:boxborderw=10:{font}[out]"
            )
        else:
            f = (
                f"{bg_filter};"
                f"[base]drawtext=text='{safe_channel}':fontcolor=white:fontsize=32:"
                f"x=(w-text_w)/2:y=490:{font},"
                f"drawtext=text='{safe_handle}':fontcolor=#FFD700:fontsize=22:"
                f"x=(w-text_w)/2:y=535:{font},"
                f"drawtext=text='{safe_title}':fontcolor=white:fontsize=32:"
                f"x=(w-text_w)/2:y=580:box=1:boxcolor=black@0.55:boxborderw=10:{font},"
                f"drawtext=text='FOLLOW FOR MORE':fontcolor=#FFD700:fontsize=24:"
                f"x=(w-text_w)/2:y=1340:box=1:boxcolor=black@0.55:boxborderw=10:{font}[out]"
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
                try:
                    os.unlink(lp)
                except Exception:
                    pass

        return output_path

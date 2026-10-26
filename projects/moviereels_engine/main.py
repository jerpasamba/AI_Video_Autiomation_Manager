import os, random, re, subprocess
from app.subprocess_utils import get_ffmpeg_cmd, no_console_kwargs

MOVIE_QUERIES = [
    "Avengers epic scene", "Spider-Man No Way Home scene",
    "Iron Man best moments", "MCU fight scene",
    "Thor Ragnarok scene", "Doctor Strange scene",
    "Black Panther scene", "Guardians of the Galaxy scene",
    "Avengers Endgame final battle",
    "Batman The Dark Knight scene", "Inception scene",
    "Interstellar scene", "John Wick scene",
    "Fast and Furious scene", "Jurassic Park scene",
]


def _search(query, max_r=5):
    import yt_dlp
    with yt_dlp.YoutubeDL({"extract_flat": True, "quiet": True, "no_warnings": True}) as ydl:
        r = ydl.extract_info(f"ytsearch{max_r}:{query}", download=False)
        return r.get("entries", [])


def _dl(url, out):
    import yt_dlp
    ydl_opts = {
        "format": "best[height<=480]",
        "outtmpl": out, "quiet": True, "no_warnings": True, "max_filesize": 50*1024*1024,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def _dur(path):
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps and fps > 0 and frames and frames > 0:
            return float(frames / fps)
    except Exception:
        pass
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", path], capture_output=True, text=True, **no_console_kwargs())
        return float(r.stdout.strip())
    except:
        return 0


def _ensure_font():
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arial.ttf")
    if not os.path.exists(local):
        src = r"C:\Windows\Fonts\arial.ttf"
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, local)
    # Relative path from project root (avoids C:\ colons — ffmpeg drawtext uses : as separator)
    me = os.path.dirname(os.path.abspath(__file__))          # .../moviereels_engine
    root = os.path.dirname(os.path.dirname(me))              # .../ (project root)
    return os.path.relpath(local, root).replace("\\", "/")


def _make_vertical(inp, out, title):
    font = _ensure_font()
    safe_title = re.sub(r'[^a-zA-Z0-9\s\-]', "", title)[:40].strip() or "Movie Clip"
    safe_channel = "ZeroBalanceManhwa"
    safe_handle = "@ZeroBalanceManhwa"

    logo_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "assets", "logo.png",
    )
    if not os.path.exists(logo_path):
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
    logo_exists = os.path.exists(logo_path)

    logo_input = []
    if logo_exists:
        lp = out.replace(".mp4", "_logo.png")
        subprocess.run([
            get_ffmpeg_cmd(), "-y", "-i", logo_path,
            "-vf", "scale=-1:130", lp,
        ], check=True, capture_output=True, **no_console_kwargs())
        logo_input = ["-i", lp]

    vid_scale = "scale=1080:-1:force_original_aspect_ratio=decrease"

    if logo_exists:
        f = (
            f"color=c=#0d0d1a:s=1080x1920:r=30,format=yuv420p[bg];"
            f"[0:v]{vid_scale}[vs];"
            f"[bg][vs]overlay=(W-w)/2:680:shortest=1[base];"
            f"[base][1:v]overlay=(W)/2-65:410[base2];"
            f"[base2]drawtext=text='{safe_channel}':fontcolor=white:fontsize=34:"
            f"x=(w-text_w)/2:y=555:fontfile={font},"
            f"drawtext=text='{safe_handle}':fontcolor=#FFD700:fontsize=22:"
            f"x=(w-text_w)/2:y=600:fontfile={font},"
            f"drawtext=text='{safe_title}':fontcolor=white:fontsize=34:"
            f"x=(w-text_w)/2:y=635:box=1:boxcolor=black@0.4:boxborderw=8:fontfile={font}[out]"
        )
    else:
        f = (
            f"color=c=#0d0d1a:s=1080x1920:r=30,format=yuv420p[bg];"
            f"[0:v]{vid_scale}[vs];"
            f"[bg][vs]overlay=(W-w)/2:680:shortest=1[base];"
            f"[base]drawtext=text='{safe_channel}':fontcolor=white:fontsize=34:"
            f"x=(w-text_w)/2:y=555:fontfile={font},"
            f"drawtext=text='{safe_handle}':fontcolor=#FFD700:fontsize=22:"
            f"x=(w-text_w)/2:y=600:fontfile={font},"
            f"drawtext=text='{safe_title}':fontcolor=white:fontsize=34:"
            f"x=(w-text_w)/2:y=635:box=1:boxcolor=black@0.4:boxborderw=8:fontfile={font}[out]"
        )

    cmd = [
        get_ffmpeg_cmd(), "-y", "-i", inp,
        *logo_input,
        "-filter_complex", f,
        "-map", "[out]",
        "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-t", "60",
        "-movflags", "+faststart", "-pix_fmt", "yuv420p", out,
    ]
    subprocess.run(cmd, check=True, **no_console_kwargs())

    if logo_exists:
        lp = out.replace(".mp4", "_logo.png")
        if os.path.exists(lp):
            try:
                os.unlink(lp)
            except OSError:
                pass


def fetch_movie_clip(search_term=None, output_dir=None):
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    queries = [search_term] + MOVIE_QUERIES if search_term else MOVIE_QUERIES
    last_error = None

    for query in queries:
        try:
            entries = _search(query)
            if not entries:
                continue
            random.shuffle(entries)
            for entry in entries:
                url = f"https://youtube.com/watch?v={entry['id']}"
                title = entry.get("title", "movie_clip")
                safe = re.sub(r'[^\w \-_]', "", title).strip()[:80] or "movie_clip"
                final = os.path.join(output_dir, f"movie_{safe}.mp4")
                if os.path.exists(final):
                    return {"path": final, "title": title, "source_url": url, "duration_sec": _dur(final)}

                raw = os.path.join(output_dir, f"movie_{safe}_raw.mp4")
                _dl(url, raw)
                try:
                    if not os.path.exists(raw):
                        continue
                    d = _dur(raw)
                    if 0 < d < 30:
                        continue
                    _make_vertical(raw, final, title)
                    if os.path.exists(final):
                        return {"path": final, "title": title, "source_url": url, "duration_sec": _dur(final)}
                finally:
                    if os.path.exists(raw):
                        try:
                            os.unlink(raw)
                        except:
                            pass
        except Exception as e:
            last_error = e

    raise RuntimeError(f"Could not fetch movie clip: {last_error}")

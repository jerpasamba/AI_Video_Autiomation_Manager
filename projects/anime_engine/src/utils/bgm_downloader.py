import os
import subprocess
import sys
import json
from src.utils.ffmpeg import FFMPEG

from app.subprocess_utils import no_console_kwargs


class YouTubeBGMDownloader:
    def __init__(self, music_dir="assets/music", playlist_url=""):
        self.music_dir = music_dir
        self.playlist_url = playlist_url
        os.makedirs(music_dir, exist_ok=True)

    def get_track_count(self):
        if not os.path.exists(self.music_dir):
            return 0
        return len([f for f in os.listdir(self.music_dir)
                    if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg'))])

    def download_tracks(self, count=10, progress_callback=None):
        def _log(msg):
            if progress_callback:
                progress_callback(msg)

        if not self.playlist_url:
            _log("No BGM playlist URL configured — skipping download")
            return []

        downloaded = []

        _log(f"Fetching tracks from playlist...")
        try:
            urls = self._list_playlist(count)
            for url, title in urls:
                if len(downloaded) >= count:
                    break

                safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
                output_path = os.path.join(self.music_dir, f"{safe_title}.mp3")

                if os.path.exists(output_path):
                    _log(f"  Already have: {title[:50]}")
                    downloaded.append(output_path)
                    continue

                _log(f"  Downloading: {title[:50]}...")
                try:
                    path = self._download_audio(url, output_path)
                    if path and os.path.exists(path):
                        downloaded.append(path)
                        _log(f"  ✅ {os.path.basename(path)}")
                except Exception as e:
                    _log(f"  ❌ Failed: {e}")

        except Exception as e:
            _log(f"  Playlist error: {e}")

        return downloaded

    def _list_playlist(self, max_results=20):
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist", "--dump-json",
            "--playlist-end", str(max_results),
            "--no-download",
            self.playlist_url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, **no_console_kwargs())
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp playlist error: {result.stderr.strip()[:200]}")

        videos = []
        for line in result.stdout.strip().splitlines():
            if line:
                info = json.loads(line)
                title = info.get("title", "Unknown")
                url = f"https://youtube.com/watch?v={info['id']}"
                duration = info.get("duration", 0)
                if 30 < duration < 600:
                    videos.append((url, title))

        return videos

    def _download_audio(self, url, output_path):
        base = os.path.splitext(output_path)[0]
        m4a_path = base + ".m4a"

        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestaudio[ext=m4a]/bestaudio",
            "--remux-video", "m4a",
            "-o", base + ".%(ext)s",
            "--no-playlist",
            "--print", "after_move:filepath",
            url
        ]

        env = os.environ.copy()
        ffmpeg_dir = os.path.dirname(FFMPEG)
        env["PATH"] = ffmpeg_dir + os.pathsep + env.get("PATH", "")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, **no_console_kwargs())
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[:200])

        actual_path = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else m4a_path
        if not os.path.exists(actual_path):
            for ext in ['.m4a', '.mp3', '.webm']:
                p = base + ext
                if os.path.exists(p):
                    actual_path = p
                    break

        return actual_path if os.path.exists(actual_path) else None

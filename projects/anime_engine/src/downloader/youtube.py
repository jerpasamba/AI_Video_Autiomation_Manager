import os
import subprocess
import sys
import json
import re

from app.subprocess_utils import no_console_kwargs


class YouTubeDownloader:
    def __init__(self, output_dir="downloads"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _is_channel_or_playlist(self, url):
        patterns = [
            r"youtube\.com/@\w+",
            r"youtube\.com/channel/",
            r"youtube\.com/playlist\?",
            r"youtube\.com/c/",
        ]
        return any(re.search(p, url) for p in patterns)

    def _extract_video_id(self, url):
        m = re.search(r"(?:v=|youtu\.be/|watch\?v=)([a-zA-Z0-9_-]{11})", url)
        return m.group(1) if m else None

    def _get_latest_video_from_channel(self, url, max_results=1):
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist", "--dump-json",
            "--playlist-end", str(max_results), "--no-download", url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, **no_console_kwargs())
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp channel error: {result.stderr}")

        lines = result.stdout.strip().splitlines()
        if not lines:
            raise RuntimeError(f"No videos found at: {url}")

        latest = json.loads(lines[0])
        video_url = f"https://youtube.com/watch?v={latest['id']}"
        return video_url, latest

    def get_video_info(self, url):
        is_channel = self._is_channel_or_playlist(url)
        if is_channel:
            video_url, _ = self._get_latest_video_from_channel(url)
            url = video_url

        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--dump-json", "--no-download", url],
            capture_output=True, text=True, **no_console_kwargs()
        )
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp error: {result.stderr}")

        lines = result.stdout.strip().splitlines()
        if not lines:
            raise RuntimeError(f"No data returned for: {url}")

        return json.loads(lines[0])

    def search_auto(self, max_results=3, progress_callback=None):
        queries = [
            "anime compilation 2025",
            "anime satisfying moments",
            "anime funny moments",
            "anime emotional scenes",
            "anime cinematic moments",
            "popular anime scenes",
            "anime edit",
        ]
        seen = set()
        results = []
        idx = 0
        total = len(queries)
        for query in queries:
            if len(results) >= max_results:
                break
            idx += 1
            pct = int((idx / total) * 30)
            if progress_callback:
                progress_callback(pct, f"Searching: {query}")
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "--flat-playlist", "--dump-json",
                "--playlist-end", str(max_results * 2),
                "--no-download",
                f"ytsearch{max_results * 2}:{query}"
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, **no_console_kwargs())
                if result.returncode != 0:
                    continue
                for line in result.stdout.strip().splitlines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    vid_id = data.get("id")
                    if vid_id and vid_id not in seen:
                        seen.add(vid_id)
                        url = f"https://youtube.com/watch?v={vid_id}"
                        results.append(url)
                        if len(results) >= max_results:
                            break
            except Exception:
                continue
        return results

    def download(self, url):
        is_channel = self._is_channel_or_playlist(url)
        actual_url = url
        video_id = self._extract_video_id(url)

        if is_channel:
            actual_url, latest = self._get_latest_video_from_channel(url)
            video_id = latest.get("id")

        info = self.get_video_info(actual_url)
        if not video_id:
            video_id = info.get("id", "unknown")

        safe_name = f"video_{video_id}"
        output_path = os.path.join(self.output_dir, f"{safe_name}.mp4")

        if os.path.exists(output_path):
            return output_path, info

        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "best[height<=720][ext=mp4]/best[height<=720]",
            "--merge-output-format", "mp4",
            "-o", f"{safe_name}.%(ext)s",
            "--no-playlist",
            "--print", "after_move:filepath",
            "-P", self.output_dir,
            actual_url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, **no_console_kwargs())
        if result.returncode != 0:
            err = (result.stderr.strip() or result.stdout.strip())
            raise RuntimeError(f"Download failed: {err[:200]}")

        actual_path = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else output_path
        if not os.path.exists(actual_path) and os.path.exists(output_path):
            actual_path = output_path

        if not os.path.exists(actual_path):
            for f in os.listdir(self.output_dir):
                if video_id in f:
                    actual_path = os.path.join(self.output_dir, f)
                    break

        if not os.path.exists(actual_path):
            raise FileNotFoundError(f"Video downloaded but file not found at: {output_path}")

        return actual_path, info

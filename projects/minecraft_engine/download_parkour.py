"""Download Minecraft parkour videos to use as backgrounds.

Each URL is saved as ``assets/parkour_N.mp4`` so the pipeline can pick
a random video each time.
"""
import subprocess
import sys
import os

from app.subprocess_utils import no_console_kwargs

URLS = [
    "https://www.youtube.com/watch?v=u7kdVe8q5zs",
    "https://www.youtube.com/watch?v=4X1hFJUmzR0",
    "https://www.youtube.com/watch?v=pBQ5ydbFyp8",
    "https://www.youtube.com/watch?v=CMDUoz4H-WA",
    "https://www.youtube.com/watch?v=8b6Y0ZQDH1o",
    "https://www.youtube.com/watch?v=XKHNv9YYWcA",
    "https://www.youtube.com/watch?v=O6F1KVxHGqM",
    "https://www.youtube.com/watch?v=MJW9Vqy5MYA",
    "https://www.youtube.com/watch?v=T2GRq4CLuSc",
    "https://www.youtube.com/watch?v=zFkIes6Lc7A",
]


def download():
    os.makedirs("assets", exist_ok=True)

    # Count existing parkour clips to pick the next index
    existing = [f for f in os.listdir("assets") if f.startswith("parkour_") and f.endswith(".mp4")]
    start_idx = len(existing) + 1

    for i, url in enumerate(URLS, start=start_idx):
        output = os.path.join("assets", f"parkour_{i}.mp4")
        if os.path.exists(output):
            print(f"Skipping {output} (already exists)")
            continue
        print(f"Downloading [{i}/{len(URLS) + start_idx - 1}]: {url}")
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "--merge-output-format", "mp4",
            "-o", output,
            "--no-playlist",
            url,
        ]
        try:
            subprocess.run(cmd, check=True, **no_console_kwargs())
            print(f"  Saved to {output}")
        except subprocess.CalledProcessError as e:
            print(f"  Failed: {e}")


if __name__ == "__main__":
    download()

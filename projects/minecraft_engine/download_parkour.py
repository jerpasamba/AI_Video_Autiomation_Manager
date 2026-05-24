"""Download a Minecraft parkour video to use as background."""
import subprocess
import sys
import os

URLS = [
    "https://www.youtube.com/watch?v=u7kdVe8q5zs",  # Minecraft Parkour Gameplay No Copyright
]

def download(output="assets/parkour.mp4"):
    os.makedirs("assets", exist_ok=True)
    url = URLS[0]
    print(f"Downloading Minecraft parkour video...")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", output,
        "--no-playlist",
        url,
    ]
    subprocess.run(cmd, check=True)
    print(f"Downloaded to {output}")

if __name__ == "__main__":
    download()

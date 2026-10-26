import yt_dlp, subprocess, os, re, glob

outdir = "projects/moviereels_engine/output"
os.makedirs(outdir, exist_ok=True)

# search for one entry
ydl = yt_dlp.YoutubeDL({"extract_flat": True, "quiet": True, "no_warnings": True})
r = ydl.extract_info("ytsearch1:Avengers Endgame final battle", download=False)
entry = r["entries"][0]
url = f"https://youtube.com/watch?v={entry['id']}"
title = entry.get("title", "clip")
safe = re.sub(r'[^\w \-_]', "", title).strip()[:80] or "clip"
print(f"Entry: {title}")
print(f"URL: {url}")

raw = os.path.join(outdir, f"{safe}_dl_raw.mp4")
final = os.path.join(outdir, f"{safe}_dl_final.mp4")

# download
ydl2 = yt_dlp.YoutubeDL({
    "format": "best[height<=480]",
    "outtmpl": raw, "quiet": True, "no_warnings": True, "max_filesize": 50*1024*1024,
})
ydl2.download([url])

if not os.path.exists(raw):
    print("Download failed")
    exit(1)

# check duration
r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "csv=p=0", raw], capture_output=True, text=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
d = float(r.stdout.strip() or 0)
print(f"Duration: {d:.0f}s")

# convert
safe_t = re.sub(r'[^a-zA-Z0-9\s\-]', "", title)[:60].strip() or "Movie Clip"
font = os.path.join(outdir, "..", "arial.ttf")
cmd = [
    "ffmpeg", "-y", "-i", raw,
    "-vf", f"scale=1080:1920:force_original_aspect_ratio=decrease,"
           f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=#0a0a0f,"
           f"drawtext=text=ZeroBalanceManhwa:fontcolor=white:fontsize=34:"
           f"x=(w-text_w)/2:y=40:fontfile={font},"
           f"drawtext=text=@ZeroBalanceManhwa:fontcolor=#FFD700:fontsize=22:"
           f"x=(w-text_w)/2:y=85:fontfile={font},"
           f"drawtext=text={safe_t}:fontcolor=white:fontsize=40:"
           f"x=(w-text_w)/2:y=H-120:box=1:boxcolor=black@0.5:boxborderw=10:fontfile={font}",
    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
    "-c:a", "aac", "-t", "60",
    "-movflags", "+faststart", "-pix_fmt", "yuv420p", final,
]
print(f"Running: ffmpeg -y -i {os.path.basename(raw)} -vf ...")
r = subprocess.run(cmd, capture_output=True, text=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
print(f"RC: {r.returncode}")
if r.returncode != 0:
    print(f"STDERR: {r.stderr[-800:]}")
else:
    sz = os.path.getsize(final) / 1024 / 1024
    print(f"OK: {final} ({sz:.0f}MB)")
    os.remove(raw)

# clean up extras
for f in glob.glob(os.path.join(outdir, "*_dl_*")):
    try: os.remove(f)
    except: pass

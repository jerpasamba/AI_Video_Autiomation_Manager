import subprocess

font = "arial.ttf"
final = "projects/moviereels_engine/output/quotes_test.mp4"

# test with single quotes around text value (like engine does)
r = subprocess.run([
    "ffmpeg", "-y",
    "-f", "lavfi", "-i", "color=c=black:s=640x480:d=5",
    "-vf", "drawtext=text='Test':fontsize=30:fontcolor=white:x=10:y=10:fontfile=arial.ttf",
    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
    final,
], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
print("Quoted test RC:", r.returncode)
if r.returncode != 0:
    print("STDERR:", r.stderr[-300:])

# test without quotes
final2 = final.replace(".mp4", "_noq.mp4")
r2 = subprocess.run([
    "ffmpeg", "-y",
    "-f", "lavfi", "-i", "color=c=black:s=640x480:d=5",
    "-vf", "drawtext=text=Test:fontsize=30:fontcolor=white:x=10:y=10:fontfile=arial.ttf",
    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
    final2,
], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
print("No-quote test RC:", r2.returncode)
if r2.returncode != 0:
    print("STDERR:", r2.stderr[-300:])

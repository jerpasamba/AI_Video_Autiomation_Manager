import subprocess

# Test absolute windows path in fontfile (like engine does)
font_abs = "C:\\VS_Code_Repositories\\AI_Video_Manager\\projects\\moviereels_engine\\arial.ttf"
final = "projects/moviereels_engine/output/path_test.mp4"

r = subprocess.run([
    "ffmpeg", "-y",
    "-f", "lavfi", "-i", "color=c=black:s=640x480:d=5",
    "-vf", f"drawtext=text=Test:fontsize=30:fontcolor=white:x=10:y=10:fontfile={font_abs}",
    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
    final,
], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
print("Abs path RC:", r.returncode)
if r.returncode != 0:
    print("STDERR:", r.stderr[-400:])
else:
    print("OK")

# Test with escaped colon
font_esc = "C\\:/VS_Code_Repositories/AI_Video_Manager/projects/moviereels_engine/arial.ttf"
final2 = final.replace(".mp4", "_esc.mp4")
r2 = subprocess.run([
    "ffmpeg", "-y",
    "-f", "lavfi", "-i", "color=c=black:s=640x480:d=5",
    "-vf", f"drawtext=text=Test:fontsize=30:fontcolor=white:x=10:y=10:fontfile={font_esc}",
    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
    final2,
], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
print("Escaped path RC:", r2.returncode)
if r2.returncode != 0:
    print("STDERR:", r2.stderr[-400:])
else:
    print("OK")

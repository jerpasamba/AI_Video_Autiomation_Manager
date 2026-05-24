from src.utils.ffmpeg import ffmpeg_cmd


class VideoCropper:
    def crop_to_vertical(self, video_path, output_path, start_time=0, end_time=None):
        duration = end_time - start_time if end_time else 0

        ffmpeg_cmd([
            "-y",
            "-ss", str(start_time),
            "-i", video_path,
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path
        ], check=True, capture_output=True, text=True)

        return output_path

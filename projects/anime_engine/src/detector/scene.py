import cv2
import numpy as np


class SceneDetector:
    def __init__(self, threshold=0.4):
        self.threshold = threshold

    def detect_scene_changes(self, video_path, sample_rate=5):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            return []

        scenes = []
        prev_hist = None
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if frame_count % sample_rate != 0:
                continue

            small = cv2.resize(frame, (80, 45))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [32], [0, 256])
            hist = cv2.normalize(hist, hist).flatten()

            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                if diff > self.threshold:
                    timestamp = frame_count / fps
                    scenes.append(timestamp)

            prev_hist = hist

        cap.release()

        scene_pairs = []
        if scenes:
            start = 0
            for t in scenes:
                if t - start > 1.0:
                    scene_pairs.append((start, t))
                start = t
            if scenes:
                last_end = scenes[-1]
                duration = total_frames / fps if fps > 0 else 0
                if duration > last_end + 1.0:
                    scene_pairs.append((last_end, duration))

        return scene_pairs

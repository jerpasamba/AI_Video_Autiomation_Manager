import numpy as np

from .motion import MotionAnalyzer
from .audio_energy import AudioEnergyDetector


class HighlightDetector:
    def __init__(self, config=None):
        cfg = config or {}
        self.motion_threshold = cfg.get("motion_threshold", 0.3)
        self.audio_threshold = cfg.get("audio_energy_threshold", 0.5)
        self.top_n = cfg.get("top_n_clips", 5)
        self.min_duration = cfg.get("clip_min_duration", 15)
        self.max_duration = cfg.get("clip_max_duration", 60)

        self.motion_analyzer = MotionAnalyzer(self.motion_threshold)
        self.audio_detector = AudioEnergyDetector(self.audio_threshold)

    def detect(self, video_path, progress_callback=None):
        if progress_callback:
            progress_callback("Scanning for action scenes...")

        motion_scores, motion_times, fps, duration = self.motion_analyzer.analyze(
            video_path, progress_callback=progress_callback
        )

        if not motion_scores or duration <= 0:
            if progress_callback:
                progress_callback("No motion data — might be a static video")
            return []

        if progress_callback:
            progress_callback("Analyzing audio for action peaks...")
        audio_scores, audio_times, sr = self.audio_detector.analyze(video_path)

        if progress_callback:
            progress_callback("Ranking best moments...")
        combined = self._combine_signals(motion_scores, motion_times, audio_scores, audio_times, duration)
        segments = self._extract_highlights(combined, duration)
        segments = self._snap_to_scene_boundaries(
            segments,
            getattr(self.motion_analyzer, 'last_scene_changes', []),
            duration
        )

        if progress_callback:
            duration_m = duration / 60
            if segments:
                progress_callback(f"Found {len(segments)} action segments in {duration_m:.0f}min video")
                for j, s in enumerate(segments):
                    start_m = int(s["start"] // 60)
                    start_s = int(s["start"] % 60)
                    end_m = int(s["end"] // 60)
                    end_s = int(s["end"] % 60)
                    progress_callback(f"  Clip {j+1}: {start_m}:{start_s:02d} - {end_m}:{end_s:02d} (action score: {s['score']:.2f})")
            else:
                progress_callback(f"No strong action moments in this {duration_m:.0f}min video — try another video")

        return segments

    def _combine_signals(self, motion_scores, motion_times, audio_scores, audio_times, duration):
        if duration <= 0:
            return []
        time_grid = np.linspace(0, duration, max(len(motion_scores), 100))

        if motion_scores:
            motion_interp = np.interp(time_grid, motion_times, motion_scores)
        else:
            motion_interp = np.zeros_like(time_grid)

        if audio_scores:
            audio_interp = np.interp(time_grid, audio_times, audio_scores)
        else:
            audio_interp = np.zeros_like(time_grid)

        combined = 0.7 * motion_interp + 0.3 * audio_interp

        return list(zip(time_grid, combined))

    def _extract_highlights(self, combined, duration):
        if not combined or duration <= 0:
            return []

        times = np.array([t for t, s in combined])
        scores = np.array([s for t, s in combined])

        if len(times) == 0:
            return []

        smoothed = np.convolve(scores, np.ones(5) / 5, mode="same")

        segments = []
        i = 0
        while i < len(times):
            if smoothed[i] > self.motion_threshold:
                start_time = times[i]
                window = int(self.max_duration * len(times) / duration)
                if window < 1:
                    window = 1
                peak_idx = i + int(np.argmax(smoothed[i:i + window]))
                peak_time = times[min(peak_idx, len(times) - 1)]

                end_time = min(peak_time + self.min_duration, duration)
                end_time = min(end_time, start_time + self.max_duration)

                if end_time - start_time >= self.min_duration:
                    seg_window = int((end_time - start_time) * len(times) / duration)
                    if seg_window < 1:
                        seg_window = 1
                    score = float(np.mean(smoothed[i:i + seg_window]))
                    segments.append({
                        "start": float(start_time),
                        "end": float(end_time),
                        "score": score
                    })

                step = int((end_time - start_time) * len(times) / duration)
                i += max(step, 1)
            else:
                i += 1

        segments.sort(key=lambda s: s["score"], reverse=True)
        segments = segments[:self.top_n]
        segments.sort(key=lambda s: s["start"])

        return segments

    def _snap_to_scene_boundaries(self, segments, scene_changes, duration):
        if not scene_changes:
            return segments

        scene_changes = sorted(scene_changes)
        snapped = []
        for seg in segments:
            end = seg["end"]
            for sc in scene_changes:
                if sc > end and sc - end < 5:
                    end = sc
                    break
            if end > duration:
                end = duration
            seg["end"] = end
            if end - seg["start"] >= self.min_duration:
                snapped.append(seg)

        return snapped

import numpy as np

from .motion import MotionAnalyzer
from .audio_energy import AudioEnergyDetector


class HighlightDetector:
    def __init__(self, config=None):
        cfg = config or {}
        self.scene_threshold = cfg.get("scene_threshold", 0.4)
        self.top_n = cfg.get("top_n_clips", 5)

        self.motion_analyzer = MotionAnalyzer(threshold=self.scene_threshold)
        self.audio_detector = AudioEnergyDetector()

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
            progress_callback("Building scene-based segments...")
        segments = self._extract_scene_segments(
            motion_scores, motion_times,
            audio_scores, audio_times,
            duration
        )

        if progress_callback:
            duration_m = duration / 60
            if segments:
                progress_callback(f"Found {len(segments)} scene segments in {duration_m:.0f}min video")
                for j, s in enumerate(segments):
                    start_m = int(s["start"] // 60)
                    start_s = int(s["start"] % 60)
                    end_m = int(s["end"] // 60)
                    end_s = int(s["end"] % 60)
                    length = s["end"] - s["start"]
                    progress_callback(f"  Scene {j+1}: {start_m}:{start_s:02d} - {end_m}:{end_s:02d} ({length:.0f}s, score: {s['score']:.2f})")
            else:
                progress_callback(f"No strong scenes in this {duration_m:.0f}min video — try another video")

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

    def _build_scene_ranges(self, scene_changes, duration):
        """Build (start, end) pairs from scene cut timestamps.

        Merges cuts closer than 2s and discards segments shorter than 3s
        to avoid micro-clips from rapid anime editing.
        """
        if not scene_changes:
            return [(0.0, duration)]

        sorted_cuts = sorted(set(scene_changes))
        ranges = []
        prev = 0.0
        for cut in sorted_cuts:
            if cut > prev + 3.0:
                if cut - prev >= 5.0:
                    ranges.append((prev, cut))
                prev = cut
        if duration - prev >= 5.0:
            ranges.append((prev, duration))
        return ranges

    def _score_scene(self, start, end, combined_times, combined_scores):
        """Score a scene segment by averaging its combined signal."""
        mask = (combined_times >= start) & (combined_times <= end)
        if not mask.any():
            return 0.0
        return float(np.mean(combined_scores[mask]))

    def _extract_scene_segments(self, motion_scores, motion_times, audio_scores, audio_times, duration):
        """Find the best scenes by scoring each natural scene segment.

        1. Get scene boundaries from FFmpeg scene detection
        2. Build segments between consecutive scene cuts
        3. Score each segment using combined motion+audio signal
        4. Pick the top N highest-scoring segments
        5. No minimum/maximum duration limits — scenes are used at natural length
        """
        scene_changes = getattr(self.motion_analyzer, 'last_scene_changes', [])
        scene_ranges = self._build_scene_ranges(scene_changes, duration)

        combined = self._combine_signals(motion_scores, motion_times, audio_scores, audio_times, duration)
        combined_times = np.array([t for t, s in combined])
        combined_scores = np.array([s for t, s in combined])

        segments = []
        for start, end in scene_ranges:
            # Skip initial publisher intro / bumper (e.g. Weekly Jump, Crunchyroll logo)
            if duration > 20.0 and start < 3.5 and end <= 6.0:
                continue
            score = self._score_scene(start, end, combined_times, combined_scores)
            segments.append({
                "start": float(start),
                "end": float(end),
                "score": score
            })

        # Sort by score descending, keep top N, then restore chronological order
        segments.sort(key=lambda s: s["score"], reverse=True)
        segments = segments[:self.top_n]
        segments.sort(key=lambda s: s["start"])

        return segments

import os
import shutil
from pathlib import Path

from src.config import Config
from src.downloader.youtube import YouTubeDownloader
from src.detector import HighlightDetector
from src.editor.crop import VideoCropper
from src.editor.intro_outro import IntroOutroGenerator
from src.editor.audio import AudioEditor
from src.editor.branding import BrandingOverlay


def _safe_filename(title, suffix="_shorts.mp4", max_len=80):
    import uuid
    uid = uuid.uuid4().hex[:8]
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title).strip()
    safe = safe[:max_len].rstrip("._- ")
    if not safe:
        safe = "anime_highlight"
    return f"{safe}_{uid}{suffix}"


class Pipeline:
    def __init__(self, config: Config):
        self.config = config
        self.downloader = YouTubeDownloader(
            output_dir=os.path.join(config["output_dir"], "downloads")
        )
        detection_config = {
            **config["scene_detection"],
        }
        self.detector = HighlightDetector(detection_config)
        self.cropper = VideoCropper()
        self.audio_editor = AudioEditor(
            music_dir="assets/music",
            music_volume=config["background_music_volume"]
        )
        self.intro_gen = IntroOutroGenerator(
            intro_text=config["intro_text"],
            outro_text=config["outro_text"]
        )
        self.branding = BrandingOverlay(
            logo_path=config.get("logo_path", "assets/logo.png"),
            channel_name=config.get("channel_name", "ZeroBalanceManhwa"),
            channel_handle=config.get("channel_handle", "@ZeroBalanceManhwa")
        )
        self._ensure_music()

    def _ensure_music(self):
        music_dir = "assets/music"
        tracks = []
        if os.path.exists(music_dir):
            tracks = [f for f in os.listdir(music_dir)
                      if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg'))]
        if not tracks:
            from src.utils.bgm_downloader import YouTubeBGMDownloader
            dl = YouTubeBGMDownloader(
                music_dir=music_dir,
                playlist_url=self.config.get("bgm_playlist_url", "")
            )
            tracks = dl.download_tracks(count=5)

    def process_url(self, url, progress_callback=None):
        def _progress(msg):
            if progress_callback:
                progress_callback(msg)

        _progress("Reloading config...")
        self.config.reload()

        _progress("Downloading video...")
        video_path, info = self.downloader.download(url)
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Downloaded file not found at: {video_path}")
        _progress(f"Downloaded: {info['title']}")

        _progress("Scanning for action scenes...")
        segments = self.detector.detect(video_path, progress_callback=_progress)
        if not segments:
            _progress("No action scenes — will take random clips from the video")
            segments = self._fallback_segments(video_path)

        _progress(f"Found {len(segments)} action segments")

        output_dir = Path(self.config["output_dir"]) / "shorts"
        output_dir.mkdir(parents=True, exist_ok=True)

        self.intro_gen = IntroOutroGenerator(
            intro_text=self.config["intro_text"],
            outro_text=self.config["outro_text"]
        )
        self.branding = BrandingOverlay(
            logo_path=self.config.get("logo_path", "assets/logo.png"),
            channel_name=self.config.get("channel_name", "ZeroBalanceManhwa"),
            channel_handle=self.config.get("channel_handle", "@ZeroBalanceManhwa")
        )

        results = []
        combine = self.config.get("combine_segments", True)

        if combine and len(segments) > 1:
            # Combine all segments into ONE video
            music_parts = []
            total_duration = 0
            for i, seg in enumerate(segments):
                _progress(f"\n--- Part {i+1}/{len(segments)} ---")
                base_name = f"{Path(video_path).stem}_part{i+1}"
                cropped_clip = str(output_dir / f"{base_name}_cropped.mp4")
                branded_clip = str(output_dir / f"{base_name}_branded.mp4")
                music_clip = str(output_dir / f"{base_name}_music.mp4")

                _progress(f"  Cropping segment ({seg['end']-seg['start']:.0f}s)...")
                self.cropper.crop_to_vertical(
                    video_path, cropped_clip,
                    start_time=seg["start"], end_time=seg["end"]
                )

                _progress("  Adding branding...")
                self.branding.add_branding(
                    cropped_clip, branded_clip,
                    anime_title=info.get("title", "Anime Highlight")[:60],
                    clip_index=i + 1,
                    total_clips=len(segments)
                )

                _progress("  Adding background music...")
                try:
                    self.audio_editor.add_background_music(branded_clip, music_clip)
                except Exception as e:
                    _progress(f"  Music failed: {e}")
                    music_clip = branded_clip

                music_parts.append(music_clip)
                total_duration += seg['end'] - seg['start']

            # Concatenate all parts
            anime_name_for_file = info.get("title", "Anime Highlight")
            final_path = str(output_dir / _safe_filename(anime_name_for_file))
            _progress(f"\n  Concatenating {len(music_parts)} parts ({total_duration:.0f}s total)...")
            self._concat_clips(music_parts, final_path, anime_title=info.get("title", "Anime Highlight")[:60], progress_callback=_progress)

            size_mb = os.path.getsize(final_path) / (1024 * 1024)
            _progress(f"  ✅ Done: {Path(final_path).name} ({size_mb:.1f}MB)")

            anime_name = info.get("title", "Anime Highlight")[:80]
            result_title = f"{anime_name} #shorts"
            # Build anime-specific tags — YouTube allows ~500 chars total
            anime_tags = ["anime", "shorts", "highlight", "animeedit", "amv"]
            source_lower = info.get("title", "").lower()
            anime_keywords = {
                "demon slayer": "demonslayer", "one piece": "onepiece",
                "attack on titan": "shingeki", "jujutsu kaisen": "jujutsukaisen",
                "naruto": "naruto", "bleach": "bleach", "dragon ball": "dragonball",
                "chainsaw man": "chainsawman", "spy x family": "spyfamily",
                "solo leveling": "solo_leveling", "vinland saga": "vinlandsaga",
                "oshi no ko": "oshinoko", "frieren": "frieren",
            }
            for keyword, tag in anime_keywords.items():
                if keyword in source_lower and tag not in anime_tags:
                    anime_tags.append(tag)
            anime_tags.append("zerobalancemanhwa")
            result_desc = (
                f"🔥 {anime_name} Best Moments\n\n"
                f"🎬 {len(segments)} scenes combined into 1 highlight reel\n\n"
                f"📺 Anime highlight brought to you by {self.config.get('channel_name', 'ZeroBalanceManhwa')}\n"
                f"{self.config.get('channel_handle', '@ZeroBalanceManhwa')}\n\n"
                + " ".join(f"#{t}" for t in anime_tags)
            )
            # Persist metadata for the Upload tab to discover
            meta_path = final_path.replace("_shorts.mp4", "_shorts_meta.json")
            import json
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"title": result_title, "description": result_desc, "tags": anime_tags}, f, ensure_ascii=False)
            results.append({
                "path": final_path,
                "title": result_title,
                "description": result_desc,
                "tags": anime_tags,
                "segments": segments
            })
        else:
            # Original mode: one clip per segment
            for i, seg in enumerate(segments):
                _progress(f"\n--- Clip {i+1}/{len(segments)} ---")
                base_name = f"{Path(video_path).stem}_clip{i+1}"
                cropped_clip = str(output_dir / f"{base_name}_cropped.mp4")
                branded_clip = str(output_dir / f"{base_name}_branded.mp4")
                music_clip = str(output_dir / f"{base_name}_music.mp4")
                final_path = str(output_dir / _safe_filename(info.get("title", "Anime Highlight"), f"_part{i+1}_shorts.mp4"))

                _progress("  Cropping to 9:16 vertical...")
                self.cropper.crop_to_vertical(
                    video_path, cropped_clip,
                    start_time=seg["start"], end_time=seg["end"]
                )
                _progress(f"  Cropped: {seg['end']-seg['start']:.0f}s")

                _progress("  Adding header/footer branding...")
                self.branding.add_branding(
                    cropped_clip, branded_clip,
                    anime_title=info.get("title", "Anime Highlight")[:60],
                    clip_index=i + 1,
                    total_clips=len(segments)
                )
                _progress("  Branding done")

                _progress("  Adding background music...")
                try:
                    self.audio_editor.add_background_music(branded_clip, music_clip)
                except Exception as e:
                    _progress(f"  Music failed: {e}")
                    music_clip = branded_clip

                _progress("  Assembling final video (with intro/outro)...")
                try:
                    self._assemble_final(music_clip, final_path, anime_title=info.get("title", "Anime Highlight")[:60], progress_callback=_progress)
                except Exception as e:
                    _progress(f"  Assembly failed: {e}")
                    shutil.copy2(music_clip, final_path)

                size_mb = os.path.getsize(final_path) / (1024 * 1024)
                _progress(f"  ✅ Done: {Path(final_path).name} ({size_mb:.1f}MB)")

                anime_name = info.get("title", "Anime Highlight")[:80]
                # Same keyword-based tags as combined mode
                anime_tags = ["anime", "shorts", "highlight", "animeedit", "amv"]
                source_lower = info.get("title", "").lower()
                anime_keywords = {
                    "demon slayer": "demonslayer", "one piece": "onepiece",
                    "attack on titan": "shingeki", "jujutsu kaisen": "jujutsukaisen",
                    "naruto": "naruto", "bleach": "bleach", "dragon ball": "dragonball",
                    "chainsaw man": "chainsawman", "spy x family": "spyfamily",
                    "solo leveling": "solo_leveling", "vinland saga": "vinlandsaga",
                    "oshi no ko": "oshinoko", "frieren": "frieren",
                }
                for keyword, tag in anime_keywords.items():
                    if keyword in source_lower and tag not in anime_tags:
                        anime_tags.append(tag)
                anime_tags.append("zerobalancemanhwa")
                part_title = f"{anime_name} - Part {i+1} #shorts"
                part_desc = (
                    f"🔥 {anime_name}\n\n"
                    f"🎬 Part {i+1}/{len(segments)}\n\n"
                    f"📺 Anime highlight brought to you by {self.config.get('channel_name', 'ZeroBalanceManhwa')}\n"
                    f"{self.config.get('channel_handle', '@ZeroBalanceManhwa')}\n\n"
                    + " ".join(f"#{t}" for t in anime_tags)
                )
                meta_path = final_path.replace("_shorts.mp4", "_shorts_meta.json")
                import json
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump({"title": part_title, "description": part_desc, "tags": anime_tags}, f, ensure_ascii=False)
                results.append({
                    "path": final_path,
                    "title": part_title,
                    "description": part_desc,
                    "tags": anime_tags,
                    "segments": seg
                })

        return results

    def _fallback_segments(self, video_path):
        """When action detection finds nothing, use FFmpeg scene detection
        to split into natural scene segments instead of arbitrary clips."""
        from src.utils.ffmpeg import ffprobe_cmd, ffmpeg_cmd
        import re
        try:
            r = ffprobe_cmd([
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ], check=True, capture_output=True, text=True)
            duration = float((r.stdout or "").strip() or "0")
        except Exception:
            duration = 0

        if duration <= 0:
            return []

        # Detect scene cuts via FFmpeg
        try:
            result = ffmpeg_cmd([
                "-i", video_path,
                "-filter:v", "select='gt(scene,0.3)',showinfo",
                "-f", "null", "-",
            ], capture_output=True, text=True)
            cuts = []
            for line in result.stderr.split("\n"):
                m = re.search(r"pts_time:([\d.]+)", line)
                if m:
                    cuts.append(float(m.group(1)))
        except Exception:
            cuts = []

        # Build segments between cuts
        segments = []
        prev = 0.0
        for c in sorted(cuts):
            if c > prev + 0.5:
                # Skip initial publisher intro / bumper (e.g. Weekly Jump, Crunchyroll logo)
                if prev == 0.0 and c <= 4.5 and duration > 20.0:
                    prev = c
                    continue
                segments.append({"start": prev, "end": c, "score": 0.5})
            prev = c
        if duration > prev + 0.5:
            segments.append({"start": prev, "end": duration, "score": 0.5})

        if not segments or len(segments) <= 1:
            return [{"start": 0.0, "end": duration, "score": 0.5}]

        return segments

    def _assemble_final(self, main_path, output_path, anime_title=None, progress_callback=None):
        import uuid
        from src.utils.ffmpeg import ffmpeg_cmd

        intro_path = None
        outro_path = None

        # Viral short-form video starts immediately on the action hook
        # Pre-roll blank title cards kill viewer retention in the first second
        if self.config.get("include_intro_card", False):
            try:
                intro_path = main_path.replace("_music.mp4", "_intro.mp4").replace("_branded.mp4", "_intro.mp4").replace("_cropped.mp4", "_intro.mp4")
                if anime_title:
                    self.intro_gen.generate_intro(intro_path, intro_text=anime_title)
                else:
                    self.intro_gen.generate_intro(intro_path)
            except Exception:
                intro_path = None

        if self.config.get("include_outro_card", False):
            try:
                outro_path = main_path.replace("_music.mp4", "_outro.mp4").replace("_branded.mp4", "_outro.mp4").replace("_cropped.mp4", "_outro.mp4")
                self.intro_gen.generate_outro(outro_path)
            except Exception:
                outro_path = None

        concat_path = str(Path(self.config["output_dir"]) / f"concat_{uuid.uuid4().hex}.txt")
        try:
            with open(concat_path, "w") as f:
                parts = []
                if intro_path and os.path.exists(intro_path):
                    parts.append(intro_path)
                if os.path.exists(main_path):
                    parts.append(main_path)
                if outro_path and os.path.exists(outro_path):
                    parts.append(outro_path)

                if not parts:
                    if os.path.exists(main_path):
                        shutil.copy2(main_path, output_path)
                        return output_path
                    raise FileNotFoundError("No clips to assemble")

                for p in parts:
                    abs_path = os.path.abspath(p).replace("'", "'\\''")
                    f.write(f"file '{abs_path}'\n")

            if progress_callback:
                progress_callback(f"  Assembling {len(parts)} clips...")

            ffmpeg_cmd([
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_path,
                "-c", "copy",
                "-movflags", "+faststart",
                output_path
            ], check=True, capture_output=True, text=True)
        finally:
            if os.path.exists(concat_path):
                os.unlink(concat_path)

        return output_path

    def _concat_clips(self, clip_paths, output_path, anime_title=None, progress_callback=None):
        """Concatenate multiple clip parts starting immediately on action hook."""
        import uuid
        from src.utils.ffmpeg import ffmpeg_cmd

        intro_path = None
        outro_path = None

        # Viral short-form video starts immediately on the action hook
        # Pre-roll blank title cards kill viewer retention in the first second
        if self.config.get("include_intro_card", False):
            try:
                intro_path = str(Path(self.config["output_dir"]) / f"intro_{uuid.uuid4().hex}.mp4")
                if anime_title:
                    self.intro_gen.generate_intro(intro_path, intro_text=anime_title)
                else:
                    self.intro_gen.generate_intro(intro_path)
            except Exception:
                intro_path = None

        if self.config.get("include_outro_card", False):
            try:
                outro_path = str(Path(self.config["output_dir"]) / f"outro_{uuid.uuid4().hex}.mp4")
                self.intro_gen.generate_outro(outro_path)
            except Exception:
                outro_path = None

        concat_path = str(Path(self.config["output_dir"]) / f"concat_{uuid.uuid4().hex}.txt")
        try:
            with open(concat_path, "w") as f:
                parts = []
                if intro_path and os.path.exists(intro_path):
                    parts.append(intro_path)
                parts.extend(clip_paths)
                if outro_path and os.path.exists(outro_path):
                    parts.append(outro_path)

                if not parts:
                    raise FileNotFoundError("No clips to assemble")

                for p in parts:
                    abs_path = os.path.abspath(p).replace("'", "'\\''")
                    f.write(f"file '{abs_path}'\n")

            if progress_callback:
                progress_callback(f"  Assembling {len(parts)} clips...")

            ffmpeg_cmd([
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_path,
                "-c", "copy",
                "-movflags", "+faststart",
                output_path
            ], check=True, capture_output=True, text=True)
        finally:
            if os.path.exists(concat_path):
                os.unlink(concat_path)

        return output_path

    def upload_clip(self, clip, progress_callback=None):
        from src.uploader.youtube import YouTubeUploader
        yt_cfg = self.config["youtube"]
        uploader = YouTubeUploader(
            client_secret_file=yt_cfg.get("client_secret_file", ""),
            token_file=yt_cfg.get("token_file", "youtube_token.json")
        )
        tags = yt_cfg.get("default_tags", ["anime", "shorts", "highlights"])
        result = uploader.upload(
            video_path=clip["path"],
            title=clip["title"],
            description=clip.get("description", ""),
            tags=tags,
            category_id=yt_cfg.get("default_category", "22")
        )
        if result:
            os.unlink(clip["path"])
            if progress_callback:
                progress_callback(f"  ✅ Uploaded & deleted: {os.path.basename(clip['path'])}")
        return result

    def cleanup_temp_files(self, keep_shorts=True):
        dirs_to_clean = [
            Path(self.config["output_dir"]) / "downloads",
        ]
        for d in dirs_to_clean:
            if d.exists():
                shutil.rmtree(str(d))

        shorts_dir = Path(self.config["output_dir"]) / "shorts"
        if shorts_dir.exists() and keep_shorts:
            for f in shorts_dir.iterdir():
                if f.is_file() and not f.name.endswith("_shorts.mp4") and not f.name.endswith("_logo_scaled.png"):
                    try:
                        f.unlink()
                    except Exception:
                        pass

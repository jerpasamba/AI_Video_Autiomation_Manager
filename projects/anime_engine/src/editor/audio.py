import os
import random
import asyncio
import edge_tts
from src.utils.ffmpeg import ffmpeg_cmd


class AudioEditor:
    def __init__(self, music_dir="assets/music", music_volume=0.3):
        self.music_dir = music_dir
        self.music_volume = music_volume
        os.makedirs(music_dir, exist_ok=True)

    def get_music_tracks(self):
        tracks = []
        if os.path.exists(self.music_dir):
            for f in os.listdir(self.music_dir):
                if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg')):
                    tracks.append(os.path.join(self.music_dir, f))
        return tracks

    def add_background_music(self, video_path, output_path, track_path=None, volume=None):
        vol = volume if volume is not None else self.music_volume

        tracks = self.get_music_tracks()

        if not tracks and track_path is None:
            ffmpeg_cmd(["-y", "-i", video_path, "-c", "copy", "-movflags", "+faststart", output_path],
                       check=True, capture_output=True)
            return output_path

        music_path = track_path if track_path else random.choice(tracks)

        ffmpeg_cmd([
            "-y",
            "-i", video_path,
            "-i", music_path,
            "-filter_complex",
            f"[1:a]volume={vol}[bgm];[0:a][bgm]amix=inputs=2:duration=first:weights=1 0.4[audio]",
            "-map", "0:v",
            "-map", "[audio]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            "-movflags", "+faststart",
            output_path
        ], check=True, capture_output=True, text=True)

        return output_path

    def _dynamic_mix(self, orig_audio, music, base_vol):
        from moviepy.audio.AudioClip import AudioArrayClip

        orig_samples = orig_audio.to_soundarray(fps=44100)
        music_samples = music.to_soundarray(fps=44100)

        min_len = min(len(orig_samples), len(music_samples))
        orig_samples = orig_samples[:min_len]
        music_samples = music_samples[:min_len]

        if orig_samples.ndim == 1:
            orig_mono = orig_samples
        else:
            orig_mono = np.mean(orig_samples, axis=1)

        frame_size = int(44100 * 0.05)
        envelope = np.zeros_like(orig_mono)
        for i in range(0, len(orig_mono), frame_size):
            chunk = orig_mono[i:i + frame_size]
            rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0
            envelope[i:i + frame_size] = rms

        env_smooth = np.convolve(envelope, np.ones(int(frame_size * 2)) / int(frame_size * 2), mode="same")

        eps = 1e-10
        env_norm = env_smooth / (np.max(env_smooth) + eps)

        # Dynamic ducking: louder original → quieter music
        # Base vol when silent, down to 0.1 when loud
        duck_factor = base_vol - (base_vol - 0.05) * env_norm
        duck_factor = np.clip(duck_factor, 0.05, base_vol)

        if music_samples.ndim == 1:
            music_scaled = music_samples * duck_factor
        else:
            music_scaled = music_samples * duck_factor[:, np.newaxis]

        orig_scaled = orig_samples
        mixed = orig_scaled + music_scaled

        peak = np.max(np.abs(mixed))
        if peak > 1.0:
            mixed = mixed / peak * 0.98

        final_clip = AudioArrayClip(mixed, fps=44100)
        return final_clip

    def add_impact_sounds(self, video_path, output_path, peak_times, sound_path=None):
        from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
        import numpy as np

        video_clip = VideoFileClip(video_path)
        orig_audio = video_clip.audio

        if sound_path and os.path.exists(sound_path):
            impact = AudioFileClip(sound_path)
        else:
            impact = self._generate_impact_sound()

        layers = [orig_audio] if orig_audio else []
        for t in peak_times:
            if t + impact.duration <= video_clip.duration:
                layers.append(impact.with_start(t).with_volume(0.6))

        if len(layers) > 1:
            final_audio = CompositeAudioClip(layers)
        else:
            final_audio = layers[0] if layers else None

        if final_audio:
            video_clip = video_clip.with_audio(final_audio)
        video_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        video_clip.close()

        return output_path

    def _generate_impact_sound(self, duration=0.3):
        from moviepy.audio.AudioClip import AudioArrayClip
        import numpy as np

        sr = 44100
        t = np.linspace(0, duration, int(sr * duration))

        # Low boom + noise burst
        boom = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 15)
        noise = np.random.randn(len(t)) * np.exp(-t * 12) * 0.3
        click = np.sin(2 * np.pi * 2000 * t) * np.exp(-t * 30) * 0.1

        samples = boom + noise + click
        samples = samples / np.max(np.abs(samples)) * 0.5

        return AudioArrayClip(samples, fps=sr)

    async def generate_voiceover(self, text, output_path, voice="en-US-JennyNeural", rate="+0%"):
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
        await communicate.save(output_path)
        return output_path

    def add_voiceover(self, video_path, voiceover_path, output_path, volume=0.7):
        from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip

        video_clip = VideoFileClip(video_path)
        orig_audio = video_clip.audio
        vo = AudioFileClip(voiceover_path).with_volume(volume)

        if orig_audio is not None:
            orig_audio = orig_audio.with_volume(0.3)
            final_audio = CompositeAudioClip([orig_audio, vo])
        else:
            final_audio = vo

        video_clip = video_clip.with_audio(final_audio)
        video_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        video_clip.close()

        return output_path

    def run_async(self, coro):
        return asyncio.run(coro)

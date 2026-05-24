import os
import numpy as np
from pydub import AudioSegment, generators


class BackgroundMusicGenerator:
    NOTE_NAMES = {
        "C": 261.63, "C#": 277.18, "D": 293.66, "D#": 311.13,
        "E": 329.63, "F": 349.23, "F#": 369.99, "G": 392.00,
        "G#": 415.30, "A": 440.00, "A#": 466.16, "B": 493.88
    }

    def __init__(self, output_dir="assets/music", sample_rate=44100):
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        os.makedirs(output_dir, exist_ok=True)

    def generate_all(self):
        tracks = [
            ("lo-fi_chill", self._lo_fi_chill),
            ("anime_hopeful", self._anime_hopeful),
            ("action_beat", self._action_beat),
            ("chill_electronic", self._chill_electronic),
            ("gentle_piano", self._gentle_piano),
            ("funk_groove", self._funk_groove),
        ]

        generated = []
        for name, gen_func in tracks:
            path = os.path.join(self.output_dir, f"{name}.mp3")
            if not os.path.exists(path):
                try:
                    track = gen_func()
                    track.export(path, format="mp3", bitrate="192k")
                    generated.append(name)
                except Exception as e:
                    print(f"  Could not generate {name}: {e}")
            else:
                generated.append(name)

        return generated

    def _make_note(self, freq, duration_ms, volume=-20):
        return generators.Sine(freq).to_audio_segment(
            duration=duration_ms, volume=volume
        )

    def _make_chord(self, freqs, duration_ms, volume=-22):
        chord = AudioSegment.silent(duration=duration_ms)
        for f in freqs:
            tone = self._make_note(f, duration_ms, volume)
            chord = chord.overlay(tone)
        return chord

    def _add_beat(self, duration_ms, bpm=85):
        beat_dur = 60000 / bpm
        track = AudioSegment.silent(duration=duration_ms)

        num_beats = int(duration_ms / beat_dur)
        kick = generators.Sine(60).to_audio_segment(duration=80, volume=-8)
        hihat = generators.Sine(8000).to_audio_segment(duration=40, volume=-18)

        for i in range(num_beats):
            pos = int(i * beat_dur)
            if i % 2 == 0:
                track = track.overlay(kick, position=pos)
            if i % 4 == 2:
                track = track.overlay(hihat, position=pos)

        return track

    def _lo_fi_chill(self, duration_ms=60000):
        bpm = 80
        chord_prog = [
            (["C4", "E4", "G4"], 2),
            (["A3", "C4", "E4"], 2),
            (["F3", "A3", "C4"], 2),
            (["G3", "B3", "D4"], 2),
        ]

        beat_dur = 60000 / bpm
        total = AudioSegment.silent(duration=duration_ms)

        for bar in range(int(duration_ms / (beat_dur * 4))):
            chord_name, beats = chord_prog[bar % len(chord_prog)]
            freqs = [self.NOTE_NAMES[n.replace("4", "").replace("3", "")]
                     * (4 if "4" in n else 2) for n in chord_name]
            chord_dur = int(beats * beat_dur)
            chord = self._make_chord(freqs, chord_dur, volume=-18)

            chord = chord.low_pass_filter(1000)
            pos = int(bar * 4 * beat_dur)
            total = total.overlay(chord, position=pos)

        beats = self._add_beat(duration_ms, bpm)
        total = total.overlay(beats, position=0)

        return total

    def _anime_hopeful(self, duration_ms=60000):
        bpm = 90
        beat_dur = 60000 / bpm
        total = AudioSegment.silent(duration=duration_ms)

        melody_notes = [
            "C5", "E5", "G5", "A5", "G5", "E5", "D5", "C5",
            "D5", "F5", "A5", "C6", "A5", "F5", "E5", "D5"
        ]

        note_dur = beat_dur

        # Pad melody
        melody = AudioSegment.silent(duration=duration_ms)
        for i, note_name in enumerate(melody_notes):
            octave = int(note_name[-1])
            base = self.NOTE_NAMES[note_name[:-1]]
            freq = base * (2 ** (octave - 4))
            pos = int(i * note_dur)
            if pos + int(note_dur) <= duration_ms:
                tone = self._make_note(freq, int(note_dur * 0.8), volume=-12)
                tone = tone.low_pass_filter(800)
                melody = melody.overlay(tone, position=pos)

        # Chord pads
        chord_prog = [
            (["C4", "E4", "G4"], 4),
            (["G4", "B4", "D5"], 4),
            (["A3", "C4", "E4"], 4),
            (["F3", "A3", "C4"], 4),
        ]

        for bar in range(int(duration_ms / (beat_dur * 4))):
            chord_name, beats = chord_prog[bar % len(chord_prog)]
            freqs = [self.NOTE_NAMES[n[:-1]] * (2 if "4" in n else 1)
                     for n in chord_name]
            chord_dur = int(beats * beat_dur)
            chord = self._make_chord(freqs, chord_dur, volume=-22)
            chord = chord.low_pass_filter(600)
            total = total.overlay(chord, position=int(bar * 4 * beat_dur))

        total = total.overlay(melody, position=0)
        beats = self._add_beat(duration_ms, bpm)
        total = total.overlay(beats.position(100), position=0)
        total = total.fade_in(2000).fade_out(3000)

        return total

    def _action_beat(self, duration_ms=60000):
        bpm = 120
        beat_dur = 60000 / bpm
        total = AudioSegment.silent(duration=duration_ms)

        # Intense kick pattern
        kick = generators.Sine(50).to_audio_segment(duration=100, volume=-6)
        snare = generators.WhiteNoise().to_audio_segment(duration=80, volume=-14)
        crash = generators.Sawtooth(2000).to_audio_segment(duration=200, volume=-22)

        for i in range(int(duration_ms / beat_dur)):
            pos = int(i * beat_dur)
            if i % 4 == 0 or i % 4 == 2:
                total = total.overlay(kick, position=pos)
            if i % 4 == 1 or i % 4 == 3:
                total = total.overlay(snare, position=pos)
            if i % 8 == 0:
                total = total.overlay(crash, position=pos)

        total = total.fade_in(1000).fade_out(3000)
        return total

    def _chill_electronic(self, duration_ms=60000):
        bpm = 100
        beat_dur = 60000 / bpm
        total = AudioSegment.silent(duration=duration_ms)

        chord_prog = [
            (["D4", "F#4", "A4"], 4),
            (["A3", "C#4", "E4"], 4),
            (["G3", "B3", "D4"], 4),
            (["E3", "G3", "B3"], 4),
        ]

        for bar in range(int(duration_ms / (beat_dur * 4))):
            chord_name, beats = chord_prog[bar % len(chord_prog)]
            freqs = [self.NOTE_NAMES[n[:-1]] * (2 if "4" in n else 1)
                     for n in chord_name]
            chord_dur = int(beats * beat_dur)
            chord = self._make_chord(freqs, chord_dur, volume=-20)
            chord = chord.low_pass_filter(1200)
            total = total.overlay(chord, position=int(bar * 4 * beat_dur))

        # Arp
        arp = AudioSegment.silent(duration=duration_ms)
        arp_notes = ["D5", "F#5", "A5", "D6", "A5", "F#5", "E5", "C#5"]
        for i, n in enumerate(arp_notes):
            octave = int(n[-1])
            base_f = self.NOTE_NAMES[n[:-1]] * (2 ** (octave - 4))
            pos = int(i * beat_dur * 0.5)
            if pos < duration_ms:
                tone = self._make_note(base_f, int(beat_dur * 0.4), volume=-16)
                tone = tone.low_pass_filter(1500)
                arp = arp.overlay(tone, position=pos)

        total = total.overlay(arp, position=0)
        beats = self._add_beat(duration_ms, bpm)
        total = total.overlay(beats, position=0)
        total = total.fade_in(2000).fade_out(3000)

        return total

    def _gentle_piano(self, duration_ms=60000):
        bpm = 70
        beat_dur = 60000 / bpm
        total = AudioSegment.silent(duration=duration_ms)

        # Simple melody using sine waves (piano-like with ADSR)
        melody = [
            ("E5", 2), ("D5", 1), ("C5", 1), ("D5", 2), ("E5", 2),
            ("C5", 2), ("A4", 2), ("G4", 2), ("A4", 2), ("C5", 2),
            ("E5", 2), ("D5", 1), ("C5", 1), ("D5", 2), ("C5", 4),
        ]

        pos = 0
        for note_name, beats in melody:
            octave = int(note_name[-1])
            base_f = self.NOTE_NAMES[note_name[:-1]] * (2 ** (octave - 4))
            dur_ms = int(beats * beat_dur)
            tone = self._make_note(base_f, dur_ms, volume=-10)
            tone = tone.low_pass_filter(500)
            total = total.overlay(tone, position=pos)
            pos += dur_ms

        total = total.fade_in(2000).fade_out(4000)
        return total

    def _funk_groove(self, duration_ms=60000):
        bpm = 105
        beat_dur = 60000 / bpm
        total = AudioSegment.silent(duration=duration_ms)

        # Funky slap bass pattern (pentatonic)
        bass_notes = [
            ("D2", 1), ("D2", 0.5), ("F2", 0.5),
            ("G2", 1), ("G2", 0.5), ("A2", 0.5),
            ("A#2", 0.5), ("A2", 0.5), ("G2", 1), ("F2", 1),
            ("D2", 1), ("D2", 0.5), ("F2", 0.5),
            ("C3", 0.5), ("A2", 0.5), ("G2", 0.5), ("F2", 0.5),
        ]

        bass_track = AudioSegment.silent(duration=duration_ms)
        pos = 0
        for note_name, beats in bass_notes:
            base_f = self.NOTE_NAMES[note_name[:-1]]
            octave = int(note_name[-1])
            freq = base_f * (2 ** (octave - 4))
            dur_ms = int(beats * beat_dur)
            tone = generators.Sine(freq).to_audio_segment(duration=max(dur_ms, 50), volume=-10)
            tone = tone.low_pass_filter(300)
            bass_track = bass_track.overlay(tone, position=pos)
            pos += dur_ms

        bass_track = bass_track.low_pass_filter(200)
        total = total.overlay(bass_track, position=0)

        # Funky wah chords (muted, staccato)
        chord_track = AudioSegment.silent(duration=duration_ms)
        chord_prog = [
            (["D4", "F4", "A4"], 2),
            (["G4", "A4", "C5"], 2),
            (["A4", "C5", "E5"], 2),
            (["F4", "A4", "C5"], 2),
        ]
        pos = 0
        for chord_notes, beats in chord_prog:
            freqs = []
            for n in chord_notes:
                base = self.NOTE_NAMES[n[:-1]]
                octave = int(n[-1])
                freqs.append(base * (2 ** (octave - 4)))
            dur_ms = int(beats * beat_dur)
            chord = AudioSegment.silent(duration=dur_ms)
            for f in freqs:
                tone = generators.Sine(f).to_audio_segment(duration=dur_ms, volume=-20)
                chord = chord.overlay(tone)
            chord = chord.low_pass_filter(2000)
            chord_track = chord_track.overlay(chord, position=pos)
            pos += dur_ms

        total = total.overlay(chord_track, position=0)

        # Funky drums with hi-hat offbeats
        drum_track = AudioSegment.silent(duration=duration_ms)
        kick = generators.Sine(55).to_audio_segment(duration=100, volume=-6)
        snare = generators.WhiteNoise().to_audio_segment(duration=60, volume=-12)
        hihat = generators.Sine(8000).to_audio_segment(duration=30, volume=-16)
        open_hat = generators.Sine(6000).to_audio_segment(duration=120, volume=-18)

        num_beats = int(duration_ms / beat_dur)
        for i in range(num_beats):
            p = int(i * beat_dur)
            if i % 4 == 0:
                drum_track = drum_track.overlay(kick, position=p)
            if i % 4 == 2:
                drum_track = drum_track.overlay(snare, position=p)
            # Offbeat hi-hats for funk feel
            if i % 2 == 0:
                drum_track = drum_track.overlay(hihat, position=p + int(beat_dur * 0.5))
            if i % 8 == 0:
                drum_track = drum_track.overlay(open_hat, position=p)

        total = total.overlay(drum_track, position=0)
        total = total.fade_in(1500).fade_out(3000)
        return total

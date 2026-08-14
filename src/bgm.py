"""
로열티 프리 배경음악 생성기 (numpy).
외부 파일 다운로드 없이 안정적으로 사용 가능.

- 4화음 코드 패드 + 베이스 + 부드러운 드럼 +
  하이햇 + 멜로디 아르페지오로 구성된 앰비언트/칠 비트.
- 분위기: 정보 전달 릴스에 어울리는 차분하고 긍정적인 느낌.
"""
from __future__ import annotations
import numpy as np


def _adsr(n: int, a: int, d: int, s: float, r: int, sr: int) -> np.ndarray:
    env = np.ones(n, dtype=np.float64)
    if a + d + r > n:
        a = int(n * 0.1); d = int(n * 0.15); r = int(n * 0.2)
    env[:a] = np.linspace(0, 1, a)
    env[a:a+d] = np.linspace(1, s, d)
    env[a+d:n-r] = s
    env[n-r:] = np.linspace(s, 0, r)
    return env


def _kick(duration: float = 0.18, sr: int = 44100,
          freq_start: float = 110.0, freq_end: float = 45.0) -> np.ndarray:
    n = int(duration * sr)
    t = np.arange(n) / sr
    freq = freq_end + (freq_start - freq_end) * np.exp(-t * 35)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    body = np.sin(phase)
    env = np.exp(-t * 12)
    click = np.exp(-t * 80) * (np.random.randn(n) * 0.4)
    return (body * env + click * 0.3)


def _hat(sr: int = 44100) -> np.ndarray:
    dur = 0.05
    length = int(dur * sr)
    noise = np.random.randn(length)
    kernel = np.ones(8) / 8
    hp = noise - np.convolve(noise, kernel, mode="same")
    env = np.exp(-np.linspace(0, 80, length))
    return hp * env * 0.25


def _snare(sr: int = 44100) -> np.ndarray:
    dur = 0.18
    length = int(dur * sr)
    noise = np.random.randn(length)
    kernel = np.ones(12) / 12
    hp = noise - np.convolve(noise, kernel, mode="same")
    tt = np.arange(length) / sr
    tone_env = np.exp(-tt * 25)
    tone = np.sin(2 * np.pi * 200 * tt) * tone_env
    env = np.exp(-tt * 18)
    return (hp * env * 0.5 + tone * 0.2)


def _pluck(freq: float, duration: float = 0.5, sr: int = 44100,
           vel: float = 0.3) -> np.ndarray:
    n = int(duration * sr)
    t = np.linspace(0, duration, n, endpoint=False)
    # Karplus-Strong-ish
    noise = np.random.randn(int(sr / freq)) * 0.5
    buf = np.zeros(n)
    buf[:len(noise)] = noise
    decay = 0.996
    for i in range(len(noise), n):
        buf[i] = decay * 0.5 * (buf[i-1] + buf[i-2])
    env = np.exp(-t * 3.0)
    return buf * env * vel


def _pad(freq: float, duration: float, sr: int = 44100,
         vel: float = 0.12) -> np.ndarray:
    n = int(duration * sr)
    t = np.linspace(0, duration, n, endpoint=False)
    # detuned sawtooth-like (additive)
    sig = np.zeros(n)
    for h, amp in [(1, 1.0), (2, 0.5), (3, 0.33), (4, 0.2)]:
        sig += amp * np.sin(2 * np.pi * freq * h * t + h * 0.3)
    sig /= 3.0
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t)
    env = np.ones(n)
    fade = int(0.4 * sr)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    return sig * lfo * env * vel


def make_bgm(duration: float, out_wav: Path, sample_rate: int = 44100,
             bpm: int = 94) -> Path:
    """
    분위기 있는 정보성 릴스용 BGM.
    코드 진행: C - Am - F - G (I-vi-IV-V, 밝고 친근함)
    """
    # 음계 (4옥타브 기준)
    def note(name: str) -> float:
        names = {"C":261.63,"D":293.66,"E":329.63,"F":349.23,
                 "G":392.00,"A":440.00,"B":493.88}
        letter = name[0]; octv = int(name[1]) if len(name)>1 else 4
        base = names[letter] * (2 ** (octv - 4))
        return base

    beat = 60.0 / bpm
    bar = beat * 4
    total_bars = int(np.ceil(duration / bar))
    out_n = int((total_bars * bar + 0.5) * sample_rate)
    audio = np.zeros(out_n, dtype=np.float64)

    # 코드 진행
    chords = [
        [note("C4"), note("E4"), note("G4"), note("B4")],
        [note("A3"), note("C4"), note("E4"), note("G4")],
        [note("F3"), note("A3"), note("C4"), note("F4")],
        [note("G3"), note("B3"), note("D4"), note("G4")],
    ]
    bass_notes = [note("C3"), note("A2"), note("F2"), note("G2")]
    # 아르페지오 패턴 (코드톤 인덱스)
    arp_pattern = [0, 2, 1, 2]

    for bar_idx in range(total_bars):
        chord = chords[bar_idx % 4]
        bass = bass_notes[bar_idx % 4]
        t0 = int(bar_idx * bar * sample_rate)

        # 패드 (한 마디 통으로)
        pad = sum(_pad(f, bar, sample_rate, vel=0.08) for f in chord)
        end = min(t0 + len(pad), out_n)
        audio[t0:end] += pad[:end-t0]

        # 베이스 (1, 3박)
        for b in [0, 2]:
            pos = int((t0 / sample_rate + b * beat) * sample_rate)
            bn = int(0.35 * sample_rate)
            if pos + bn <= out_n:
                tt = np.arange(bn) / sample_rate
                sig = np.sin(2 * np.pi * bass * tt) * np.exp(-tt * 4)
                audio[pos:pos+bn] += sig * 0.25

        # 드럼 (4-on-the-floor)
        for beat_idx in range(4):
            pos = int((t0 / sample_rate + beat_idx * beat) * sample_rate)
            # kick every beat
            klen = int(0.2 * sample_rate)
            if pos + klen <= out_n:
                k = _kick(0.2, sample_rate)
                audio[pos:pos+klen] += k[:klen] * 0.4
            # off-beat hats
            hpos = pos + int(beat * 0.5 * sample_rate)
            hhat = _hat(sample_rate)
            hlen = min(len(hhat), out_n - hpos)
            if hpos < out_n and hlen > 0:
                audio[hpos:hpos+hlen] += hhat[:hlen] * 0.6
            # snare on 2 and 4
            if beat_idx in (1, 3):
                sn = _snare(sample_rate)
                slen = min(len(sn), out_n - pos)
                if pos < out_n and slen > 0:
                    audio[pos:pos+slen] += sn[:slen] * 0.25

        # 아르페지오 (8분음표 4개)
        for i, cidx in enumerate(arp_pattern):
            pos = int((t0 / sample_rate + i * beat * 0.5) * sample_rate)
            freq = chord[cidx] * 2
            tone = _pluck(freq, beat * 0.7, sample_rate, vel=0.12)
            end2 = min(pos + len(tone), out_n)
            if pos < out_n:
                audio[pos:end2] += tone[:end2-pos]

    # Fade in/out + soft clip
    fade = int(0.6 * sample_rate)
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    # gentle compression / normalize
    audio = np.tanh(audio * 0.9)
    audio = audio / max(1e-6, np.max(np.abs(audio))) * 0.30

    stereo = np.stack([audio, audio], axis=1)
    arr = (stereo * 32767).astype(np.int16)
    import wave
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(arr.tobytes())
    return out_wav

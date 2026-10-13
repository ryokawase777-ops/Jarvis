"""声（読み上げ）。文ごとに合成しながら順番に再生する

エンジン（.env の TTS_ENGINE / TTS_ENGINE_JARVIS など）:
  edge       … 無料の標準音声
  voicevox   … AivisSpeech / VOICEVOX（PC上で動く無料エンジン）
  elevenlabs … ElevenLabs（最高品質・有料）
VOICE_FX_JARVIS=on で、AIらしい響き（金属的な部屋鳴り＋厚み）を付ける。
うまく合成できなかったときは自動で edge に切り替えて話す。
"""
import asyncio
import io
import os
import queue
import re
import tempfile
import threading
import time
import wave

import edge_tts
import httpx
import numpy as np
import pygame
import sounddevice as sd

import config
from personas import Persona

_CLEAN = re.compile(r"[*#`>_~|\[\]]|^\s*[-・]\s*", re.MULTILINE)


def _tmp(suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


# ---------- 音の加工 ----------
def _write_wav(samples: np.ndarray, sr: int) -> str:
    path = _tmp(".wav")
    pcm = np.clip(samples, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((pcm * 32767).astype(np.int16).tobytes())
    return path


def _read_wav_bytes(data: bytes):
    with wave.open(io.BytesIO(data), "rb") as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


_IR_CACHE: dict = {}


def _impulse(sr: int) -> np.ndarray:
    """小さく硬い部屋（スーツの中・ラボ）の残響"""
    if sr not in _IR_CACHE:
        rng = np.random.default_rng(7)
        n = int(sr * 0.22)
        t = np.arange(n) / sr
        ir = rng.standard_normal(n) * np.exp(-t / 0.045)
        # 金属的な響き：短い周期の反射を少し足す
        for d_ms, g in ((2.9, 0.5), (4.7, 0.35), (7.3, 0.25)):
            d = int(sr * d_ms / 1000)
            ir[d:] += ir[:-d] * g
        ir[0] = 0
        _IR_CACHE[sr] = ir / np.abs(ir).sum() * 6
    return _IR_CACHE[sr]


def ai_fx(x: np.ndarray, sr: int, amount: float) -> np.ndarray:
    """AIらしい響き：二重化（厚み）＋硬い部屋鳴り"""
    if amount <= 0 or x.size == 0:
        return x
    tail = int(sr * 0.25)
    x = np.concatenate([x, np.zeros(tail, dtype=np.float32)])
    # 厚み：ごく短くずらした音を重ねる
    d = int(sr * 0.011)
    doubled = x.copy()
    doubled[d:] += x[:-d] * 0.35 * amount
    # 部屋鳴り
    ir = _impulse(sr)
    n = doubled.size + ir.size - 1
    nfft = 1 << (n - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(doubled, nfft) * np.fft.rfft(ir, nfft), nfft)[: x.size]
    y = doubled + wet * 0.35 * amount
    # 低音を少し削って、すっきりした機械っぽさに
    win = max(1, sr // 240)  # 約120Hz以下をざっくり取り除く
    c = np.cumsum(np.concatenate([[0.0], y]))
    low = (c[win:] - c[:-win]) / win
    low = np.concatenate([np.full(win - 1, low[0]), low])
    hp = y - low
    y = y * (1 - 0.4 * amount) + hp * 0.4 * amount
    peak = np.abs(y).max()
    return y / peak * 0.9 if peak > 0 else y


# ---------- 各エンジン ----------
def _synth_edge(text: str, persona: Persona) -> str:
    path = _tmp(".mp3")
    comm = edge_tts.Communicate(text, persona.voice, rate=persona.rate, pitch=persona.pitch)
    asyncio.run(comm.save(path))
    return path


def _synth_elevenlabs(text: str, persona: Persona) -> str:
    voice_id = config.ELEVENLABS_VOICES[persona.key]
    sr = 24000
    r = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        params={"output_format": f"pcm_{sr}"},
        headers={"xi-api-key": config.ELEVENLABS_API_KEY},
        json={
            "text": text,
            "model_id": config.ELEVENLABS_MODEL,
            "voice_settings": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.0},
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:200]}")
    x = np.frombuffer(r.content, dtype=np.int16).astype(np.float32) / 32768
    if config.VOICE_FX[persona.key]:
        x = ai_fx(x, sr, config.VOICE_FX_AMOUNT)
    return _write_wav(x, sr)


def _synth_voicevox(text: str, persona: Persona) -> str:
    speaker = config.VOICEVOX_SPEAKERS[persona.key]
    if not speaker:
        raise RuntimeError(f"VOICEVOX_SPEAKER_{persona.key.upper()} が未設定です（list_voices.bat で番号を確認）")
    base = config.VOICEVOX_URL
    q = httpx.post(f"{base}/audio_query", params={"text": text, "speaker": speaker}, timeout=30)
    q.raise_for_status()
    query = q.json()
    query["speedScale"] = config.VOICEVOX_SPEED
    w = httpx.post(f"{base}/synthesis", params={"speaker": speaker}, json=query, timeout=60)
    w.raise_for_status()
    x, sr = _read_wav_bytes(w.content)
    if config.VOICE_FX[persona.key]:
        x = ai_fx(x, sr, config.VOICE_FX_AMOUNT)
    return _write_wav(x, sr)


ENGINES = {"edge": _synth_edge, "elevenlabs": _synth_elevenlabs, "voicevox": _synth_voicevox}


def check_engine() -> None:
    """起動時に設定を確認して知らせる"""
    used = set(config.TTS_ENGINES.values())
    for k, eng in config.TTS_ENGINES.items():
        print(f"[声] {k.upper():<6}: {eng}" + ("（AIエフェクト）" if config.VOICE_FX[k] and eng != "edge" else ""))
    for eng in used - set(ENGINES):
        print(f"[声] {eng} は不明なエンジンです。標準の声を使います。")
    if "elevenlabs" in used and not config.ELEVENLABS_API_KEY:
        print("[声] ELEVENLABS_API_KEY が未設定です。標準の声を使います。")
    if "voicevox" in used:
        try:
            httpx.get(f"{config.VOICEVOX_URL}/version", timeout=3).raise_for_status()
            print(f"[声] AivisSpeech / VOICEVOX に接続しました")
        except Exception:
            print(f"[声] {config.VOICEVOX_URL} に接続できません。AivisSpeech を先に起動してください。")


# ---------- 再生の仕組み ----------
class Speaker:
    def __init__(self):
        pygame.mixer.init()
        self._synth_q: queue.Queue = queue.Queue()
        self._play_q: queue.Queue = queue.Queue()
        self._warned: set = set()
        check_engine()
        threading.Thread(target=self._synth_worker, daemon=True).start()
        threading.Thread(target=self._play_worker, daemon=True).start()

    def say(self, text: str, persona: Persona) -> None:
        text = _CLEAN.sub("", text).strip()
        if text:
            self._synth_q.put((text, persona))

    def wait(self) -> None:
        """話し終わるまで待つ"""
        self._synth_q.join()
        self._play_q.join()

    def _synth(self, text: str, persona: Persona) -> str:
        name = config.TTS_ENGINES.get(persona.key, "edge")
        engine = ENGINES.get(name, _synth_edge)
        if engine is _synth_edge:
            return _synth_edge(text, persona)
        try:
            return engine(text, persona)
        except Exception as e:
            if name not in self._warned:
                print(f"\n[声] {name} でエラー: {e}\n[声] 標準の声で代わりに話します。")
                self._warned.add(name)
            return _synth_edge(text, persona)

    def _synth_worker(self) -> None:
        while True:
            text, persona = self._synth_q.get()
            try:
                self._play_q.put(self._synth(text, persona))
            except Exception as e:
                print(f"\n[音声合成エラー] {e}")
            finally:
                self._synth_q.task_done()

    def _play_worker(self) -> None:
        while True:
            path = self._play_q.get()
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.03)
                pygame.mixer.music.unload()
            except Exception as e:
                print(f"\n[再生エラー] {e}")
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
                self._play_q.task_done()


def chime(up: bool = True) -> None:
    """呼ばれたときの合図音（up=False で終了音）"""
    sr = 24000
    notes = (880, 1320) if up else (1320, 880)
    parts = []
    for f in notes:
        t = np.linspace(0, 0.09, int(sr * 0.09), endpoint=False)
        env = np.minimum(1, np.linspace(3, 0, t.size))
        parts.append(0.25 * np.sin(2 * np.pi * f * t) * env)
    sd.play(np.concatenate(parts).astype(np.float32), sr)
    sd.wait()

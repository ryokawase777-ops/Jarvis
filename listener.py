"""話しかけられた内容を録音して文字にする"""
from collections import deque
from typing import Optional

import numpy as np
import sounddevice as sd

import config

BLOCK = 480  # 30ms
BLOCK_SEC = BLOCK / config.SAMPLE_RATE

# 無音のときにWhisperがよく作り出す決まり文句
HALLUCINATIONS = ("ご視聴ありがとうございました", "チャンネル登録", "字幕", "最後までご視聴")


def record_utterance(start_timeout: float = 8.0, max_seconds: float = 30.0) -> Optional[np.ndarray]:
    """話し始めを待って録音し、黙ったら止める。何も話されなければ None"""
    frames = []
    preroll = deque(maxlen=10)  # 話し始めの頭切れ防止（約0.3秒）
    started = False
    waited = silent = total = 0.0

    with sd.InputStream(samplerate=config.SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCK) as stream:
        # 周囲の雑音レベルを測ってしきい値を決める
        noise = []
        for _ in range(6):
            data, _ = stream.read(BLOCK)
            noise.append(_rms(data))
        threshold = max(config.SPEECH_RMS_THRESHOLD, float(np.median(noise)) * 2.5)

        while True:
            data, _ = stream.read(BLOCK)
            chunk = data[:, 0].copy()
            loud = _rms(data) > threshold

            if not started:
                preroll.append(chunk)
                if loud:
                    started = True
                    frames.extend(preroll)
                else:
                    waited += BLOCK_SEC
                    if waited >= start_timeout:
                        return None
                continue

            frames.append(chunk)
            total += BLOCK_SEC
            silent = 0.0 if loud else silent + BLOCK_SEC
            if silent >= config.SILENCE_SECONDS or total >= max_seconds:
                break

    if total < 0.3:  # 短すぎる物音は無視
        return None
    return np.concatenate(frames)


def _rms(data: np.ndarray) -> float:
    return float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))


class Transcriber:
    def __init__(self):
        from faster_whisper import WhisperModel

        compute_type = "float16" if config.WHISPER_DEVICE == "cuda" else "int8"
        self.model = WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=compute_type)

    def transcribe(self, audio: np.ndarray) -> str:
        audio_f = audio.astype(np.float32) / 32768.0
        segments, _ = self.model.transcribe(audio_f, language="ja", beam_size=1, vad_filter=True)
        text = "".join(s.text for s in segments).strip()
        if any(h in text for h in HALLUCINATIONS) and len(text) < 25:
            return ""
        return text

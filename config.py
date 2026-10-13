"""設定の読み込み（.env から）"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    value = (os.getenv(name) or "").strip()
    return value or default  # 空欄なら既定値


# --- Claude ---
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = _get("CLAUDE_MODEL", "claude-sonnet-5-5")
MAX_HISTORY_TURNS = int(_get("MAX_HISTORY_TURNS", "20"))  # 覚えておく往復数

# --- ウェイクワード ---
# auto: Picovoiceのキーがあれば porcupine（「ジャービス」）、なければ openwakeword（「ヘイ、ジャービス」）
WAKEWORD_ENGINE = _get("WAKEWORD_ENGINE", "auto").lower()
PICOVOICE_ACCESS_KEY = _get("PICOVOICE_ACCESS_KEY")
WAKEWORD_SENSITIVITY = float(_get("WAKEWORD_SENSITIVITY", "0.6"))  # 0〜1。上げるほど反応しやすい

# --- 音声認識（Whisper） ---
WHISPER_MODEL = _get("WHISPER_MODEL", "small")   # tiny / base / small / medium / large-v3
WHISPER_DEVICE = _get("WHISPER_DEVICE", "cpu")   # cpu / cuda

# --- 録音 ---
SAMPLE_RATE = 16000
SPEECH_RMS_THRESHOLD = int(_get("SPEECH_RMS_THRESHOLD", "500"))  # 声とみなす音量の下限
SILENCE_SECONDS = float(_get("SILENCE_SECONDS", "1.0"))          # この秒数黙ったら話し終わり
FOLLOWUP_SECONDS = float(_get("FOLLOWUP_SECONDS", "6"))          # 返答後、呼ばずに続けて話せる時間

# --- 呼び方 ---
USER_CALL = _get("USER_CALL")  # 空ならキャラごとの既定（JARVIS:サー / FRIDAY:ボス / EDITH:サー）

# --- 音声合成（声） ---
# edge: 無料（標準の声） / voicevox: AivisSpeech または VOICEVOX（無料・PC上で動く） / elevenlabs: 最高品質（有料・無料枠あり）
TTS_ENGINE = _get("TTS_ENGINE", "edge").lower()

# ElevenLabs
ELEVENLABS_API_KEY = _get("ELEVENLABS_API_KEY")
ELEVENLABS_MODEL = _get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVENLABS_VOICES = {
    "jarvis": _get("ELEVENLABS_VOICE_JARVIS", "JBFqnCBsd6RMkjVDRZzb"),  # George（落ち着いた英国紳士）
    "friday": _get("ELEVENLABS_VOICE_FRIDAY", "XB0fDUnXU5powFXDhCwa"),  # Charlotte
    "edith": _get("ELEVENLABS_VOICE_EDITH", "Xb7hH8MSUJpSbSDYk0k2"),    # Alice
}

# AivisSpeech（http://127.0.0.1:10101） / VOICEVOX（http://127.0.0.1:50021）
VOICEVOX_URL = _get("VOICEVOX_URL", "http://127.0.0.1:10101").rstrip("/")
VOICEVOX_SPEAKERS = {
    "jarvis": _get("VOICEVOX_SPEAKER_JARVIS"),
    "friday": _get("VOICEVOX_SPEAKER_FRIDAY"),
    "edith": _get("VOICEVOX_SPEAKER_EDITH"),
}
VOICEVOX_SPEED = float(_get("VOICEVOX_SPEED", "1.05"))

# キャラごとに声のエンジンを変える（空なら TTS_ENGINE と同じ）
TTS_ENGINES = {k: _get(f"TTS_ENGINE_{k.upper()}", TTS_ENGINE).lower() for k in ("jarvis", "friday", "edith")}

# AIらしい響き（on / off）
VOICE_FX = {k: _get(f"VOICE_FX_{k.upper()}", "on" if k == "jarvis" else "off").lower() == "on"
            for k in ("jarvis", "friday", "edith")}
VOICE_FX_AMOUNT = float(_get("VOICE_FX_AMOUNT", "0.5"))  # 0〜1。大きいほど機械っぽく響く

"""使える声の一覧を表示する（.env の TTS_ENGINE に合わせて）"""
import httpx

import config


def voicevox():
    try:
        speakers = httpx.get(f"{config.VOICEVOX_URL}/speakers", timeout=5).json()
    except Exception:
        print(f"{config.VOICEVOX_URL} に接続できません。AivisSpeech / VOICEVOX を起動してから実行してください。")
        return
    print("番号        話者 / スタイル")
    print("-" * 40)
    for sp in speakers:
        for st in sp["styles"]:
            print(f"{st['id']:<11} {sp['name']} / {st['name']}")
    print("\n気に入った声の番号を .env の VOICEVOX_SPEAKER_JARVIS などに書いてください。")


def elevenlabs():
    if not config.ELEVENLABS_API_KEY:
        print(".env に ELEVENLABS_API_KEY を設定してください。")
        return
    r = httpx.get("https://api.elevenlabs.io/v1/voices",
                  headers={"xi-api-key": config.ELEVENLABS_API_KEY}, timeout=15)
    if r.status_code != 200:
        print(f"エラー {r.status_code}: {r.text[:200]}")
        return
    print("voice_id                 名前 / 特徴")
    print("-" * 60)
    for v in r.json().get("voices", []):
        labels = ", ".join(f"{v2}" for v2 in (v.get("labels") or {}).values())
        print(f"{v['voice_id']:<24} {v['name']} / {labels}")
    print("\n気に入った声の voice_id を .env の ELEVENLABS_VOICE_JARVIS などに書いてください。")


if __name__ == "__main__":
    used = set(config.TTS_ENGINES.values())
    if "voicevox" in used:
        print("===== AivisSpeech / VOICEVOX =====")
        voicevox()
        print()
    if "elevenlabs" in used:
        print("===== ElevenLabs =====")
        elevenlabs()
    if not used & {"voicevox", "elevenlabs"}:
        print(".env の TTS_ENGINE を voicevox か elevenlabs にしてから実行してください。")

"""JARVIS 常駐型 音声アシスタント（第1段階）

「ジャービス」と呼ぶ → ピコンと鳴る → 話しかける → 音声で返答
返答後しばらくは、呼ばずにそのまま続けて話せます。
"""
import re
import sys

import anthropic

import config
from brain import Brain
from listener import Transcriber, record_utterance
from personas import PERSONAS
from voice import Speaker, chime
from wakeword import WakeWordDetector

SENTENCE_END = re.compile(r"[。！？!?\n]")
END_WORDS = ("以上です", "以上で", "もう大丈夫", "ありがとう以上", "おやすみ", "下がっていい")
SHUTDOWN_WORDS = ("システム終了", "シャットダウン")
SWITCH_WORDS = ("代わって", "かわって", "変わって", "交代", "呼んで", "出して")


def find_switch(text: str, current: str):
    """「フライデーに代わって」などを検出して交代先のキーを返す"""
    if not any(w in text for w in SWITCH_WORDS):
        return None
    lower = text.lower()
    for key, p in PERSONAS.items():
        if key != current and any(a in lower for a in p.aliases):
            return key
    return None


def answer(brain: Brain, text: str, speaker: Speaker) -> None:
    persona = brain.persona
    print(f"{persona.display}: ", end="", flush=True)
    buf = ""
    try:
        for chunk in brain.respond_stream(text):
            print(chunk, end="", flush=True)
            buf += chunk
            while (m := SENTENCE_END.search(buf)):
                speaker.say(buf[: m.end()], persona)
                buf = buf[m.end():]
        if buf.strip():
            speaker.say(buf, persona)
    except anthropic.APIError as e:
        print(f"\n[APIエラー] {e}")
        speaker.say("申し訳ありません、通信に問題が発生しました。", persona)
    print()
    speaker.wait()


def main() -> None:
    if not config.ANTHROPIC_API_KEY:
        print("エラー: .env に ANTHROPIC_API_KEY を設定してください。")
        sys.exit(1)

    print("起動中… 音声認識モデルを読み込んでいます（初回はダウンロードに数分かかります）")
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    brains = {k: Brain(p, client) for k, p in PERSONAS.items()}
    transcriber = Transcriber()
    detector = WakeWordDetector()
    speaker = Speaker()

    current = "jarvis"
    p = PERSONAS[current]
    speaker.say(p.greeting.format(call=p.call), p)
    speaker.wait()

    try:
        while True:
            print(f"\n待機中…「{detector.phrase}」と呼んでください（終了: Ctrl+C）")
            detector.wait()
            chime(up=True)

            followup = False
            while True:
                print("聞いています…" if not followup else "（続けてどうぞ）")
                audio = record_utterance(start_timeout=config.FOLLOWUP_SECONDS if followup else 8.0)
                if audio is None:
                    if followup:
                        chime(up=False)
                    break

                text = transcriber.transcribe(audio)
                if not text:
                    break
                print(f"あなた: {text}")
                persona = PERSONAS[current]

                if any(w in text for w in SHUTDOWN_WORDS):
                    speaker.say(f"システムを終了します。お疲れさまでした、{persona.call}。", persona)
                    speaker.wait()
                    return

                if any(w in text.replace("、", "") for w in END_WORDS):
                    speaker.say("かしこまりました。", persona)
                    speaker.wait()
                    break

                new_key = find_switch(text, current)
                if new_key:
                    current = new_key
                    np_ = PERSONAS[current]
                    print(f"→ {np_.display} に交代")
                    speaker.say(np_.greeting.format(call=np_.call), np_)
                    speaker.wait()
                    followup = True
                    continue

                answer(brains[current], text, speaker)
                followup = True
    except KeyboardInterrupt:
        print("\n終了します。")
    finally:
        detector.close()


if __name__ == "__main__":
    main()

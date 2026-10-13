"""JARVIS 常駐型 音声アシスタント（第1段階）

「ジャービス」と呼ぶ → ピコンと鳴る → 話しかける → 音声で返答
返答後しばらくは、呼ばずにそのまま続けて話せます。
「開発モード」と言うと、それ以降の発言はパソコンの Claude Code に開発の依頼として渡します。
"""
import re
import sys

import config
from brain import Brain, BrainError, make_llm
from claude_code import ClaudeCode, ClaudeCodeError
from listener import Transcriber, record_utterance
from personas import PERSONAS
from voice import Speaker, chime
from wakeword import WakeWordDetector

SENTENCE_END = re.compile(r"[。！？!?\n]")
END_WORDS = ("以上です", "以上で", "もう大丈夫", "ありがとう以上", "おやすみ", "下がっていい")
SHUTDOWN_WORDS = ("システム終了", "シャットダウン")
SWITCH_WORDS = ("代わって", "かわって", "変わって", "交代", "呼んで", "出して")
DEV_START_WORDS = ("開発モード",)
DEV_END_WORDS = ("開発モード終了", "開発モードを終了", "開発モードおわり", "開発モード終わり", "開発終了")
CLAUDE_CODE_WORDS = ("クロードコード", "claudecode")  # 開発モード外でも、この言葉が入っていれば一回だけ頼む


def _norm(text: str) -> str:
    """聞き取り結果の表記ゆれ（空白・句読点・中黒）をそろえる"""
    return re.sub(r"[\s、。・,.!！?？]", "", text).lower()


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
    except BrainError as e:
        print(f"\n[エラー] {e}")
        speaker.say("申し訳ありません、頭脳との通信に問題が発生しました。", persona)
    print()
    speaker.wait()


def ask_claude_code(coder: ClaudeCode, text: str, persona, speaker: Speaker) -> None:
    """開発の依頼を Claude Code に渡し、結果を読み上げる"""
    speaker.say(f"承知しました、{persona.call}。開発担当に依頼します。終わったらお知らせします。", persona)
    speaker.wait()
    print("Claude Code 作業中…（数分かかることがあります）")
    try:
        result = coder.ask(text)
    except ClaudeCodeError as e:
        print(f"[Claude Code エラー] {e}")
        speaker.say("申し訳ありません、開発担当の作業がうまくいきませんでした。画面のメッセージを確認してください。", persona)
        speaker.wait()
        return
    print(f"Claude Code: {result}")
    for sentence in re.split(r"(?<=[。！？!?\n])", result):
        if sentence.strip():
            speaker.say(sentence, persona)
    speaker.wait()


def main() -> None:
    try:
        llm = make_llm()
        llm.check()
    except BrainError as e:
        print(f"エラー: {e}")
        sys.exit(1)

    print(f"頭脳: {llm.name}")
    coder = ClaudeCode()
    if not coder.available():
        print("注意: Claude Code が見つからないため、開発モードは使えません。")

    print("起動中… 音声認識モデルを読み込んでいます（初回はダウンロードに数分かかります）")
    brains = {k: Brain(p, llm) for k, p in PERSONAS.items()}
    transcriber = Transcriber()
    detector = WakeWordDetector()
    speaker = Speaker()

    current = "jarvis"
    dev_mode = False
    p = PERSONAS[current]
    speaker.say(p.greeting.format(call=p.call), p)
    speaker.wait()

    try:
        while True:
            mode = "【開発モード】" if dev_mode else ""
            print(f"\n{mode}待機中…「{detector.phrase}」と呼んでください（終了: Ctrl+C）")
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

                norm = _norm(text)
                if any(w in norm for w in DEV_END_WORDS):
                    dev_mode = False
                    print("→ 開発モード終了")
                    speaker.say("開発モードを終了します。", persona)
                    speaker.wait()
                    followup = True
                    continue

                if any(w in norm for w in DEV_START_WORDS):
                    if not coder.available():
                        speaker.say("申し訳ありません、Claude Code が見つからないため、開発モードは使えません。", persona)
                        speaker.wait()
                        followup = True
                        continue
                    dev_mode = True
                    coder.new_session()
                    print("→ 開発モード開始（以降の発言は Claude Code に渡します）")
                    speaker.say("開発モードに入ります。作りたいものや直したいところをどうぞ。", persona)
                    speaker.wait()
                    followup = True
                    continue

                if coder.available() and (dev_mode or any(w in norm for w in CLAUDE_CODE_WORDS)):
                    ask_claude_code(coder, text, persona, speaker)
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

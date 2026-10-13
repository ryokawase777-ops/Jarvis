"""頭脳（会話の返答を考える）

エンジン（.env の LLM_ENGINE）:
  ollama … Ollama（PC上で動く・無料）
  claude … Claude API（従量課金）
"""
import json
from datetime import datetime
from typing import Iterator

import httpx

import config
from personas import Persona

WEEKDAYS = "月火水木金土日"


class BrainError(Exception):
    """返答を作れなかったときのエラー（メッセージはそのまま画面に表示する）"""


class OllamaLLM:
    name = "Ollama"

    def check(self) -> None:
        """起動時の確認：Ollama が動いていて、モデルが入っているか"""
        try:
            r = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
            r.raise_for_status()
        except httpx.HTTPError:
            raise BrainError(
                f"Ollama に接続できません（{config.OLLAMA_URL}）。\n"
                "Ollama を起動してから、もう一度 start_jarvis.bat を実行してください。"
            )
        names = {m.get("name", "") for m in r.json().get("models", [])}
        model = config.OLLAMA_MODEL
        if model not in names and f"{model}:latest" not in names:
            raise BrainError(
                f"Ollama にモデル「{model}」が入っていません。\n"
                f"コマンドプロンプトで  ollama pull {model}  を実行してください。"
            )

    def stream(self, system: str, messages: list[dict]) -> Iterator[str]:
        payload = {
            "model": config.OLLAMA_MODEL,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": True,
            "keep_alive": "30m",  # 30分はモデルを読み込んだままにして、返答を速くする
            "options": {"num_predict": 512},
        }
        try:
            with httpx.stream("POST", f"{config.OLLAMA_URL}/api/chat", json=payload,
                              timeout=httpx.Timeout(120, connect=5)) as r:
                if r.status_code != 200:
                    r.read()
                    raise BrainError(f"Ollama エラー {r.status_code}: {r.text[:200]}")
                for line in r.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise BrainError(f"Ollama エラー: {data['error']}")
                    text = data.get("message", {}).get("content", "")
                    if text:
                        yield text
                    if data.get("done"):
                        break
        except httpx.ConnectError:
            raise BrainError("Ollama に接続できません。Ollama が起動しているか確認してください。")
        except httpx.HTTPError as e:
            raise BrainError(f"Ollama との通信に失敗しました: {e}")


class ClaudeLLM:
    name = "Claude API"

    def __init__(self):
        import anthropic
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def check(self) -> None:
        if not config.ANTHROPIC_API_KEY:
            raise BrainError(".env に ANTHROPIC_API_KEY を設定してください。")

    def stream(self, system: str, messages: list[dict]) -> Iterator[str]:
        try:
            with self.client.messages.stream(
                model=config.CLAUDE_MODEL,
                max_tokens=1024,
                system=system,
                messages=messages,
            ) as stream:
                yield from stream.text_stream
        except self._anthropic.APIError as e:
            raise BrainError(f"Claude API エラー: {e}")


def make_llm():
    if config.LLM_ENGINE == "claude":
        return ClaudeLLM()
    if config.LLM_ENGINE == "ollama":
        return OllamaLLM()
    raise BrainError(f".env の LLM_ENGINE は ollama か claude にしてください（今は「{config.LLM_ENGINE}」）。")


class Brain:
    def __init__(self, persona: Persona, llm):
        self.persona = persona
        self.llm = llm
        self.history: list[dict] = []

    def _system(self) -> str:
        now = datetime.now()
        stamp = now.strftime(f"%Y年%m月%d日（{WEEKDAYS[now.weekday()]}）%H時%M分")
        return self.persona.system_prompt() + f"\n# 現在日時\n{stamp}"

    def respond_stream(self, user_text: str) -> Iterator[str]:
        """返答を少しずつ返す（読み上げを早く始めるため）"""
        self.history.append({"role": "user", "content": user_text})
        full = ""
        try:
            for text in self.llm.stream(self._system(), self.history):
                full += text
                yield text
        except Exception:
            self.history.pop()  # 失敗した発言は履歴から外す
            raise
        self.history.append({"role": "assistant", "content": full})
        self._trim()

    def _trim(self) -> None:
        limit = config.MAX_HISTORY_TURNS * 2
        if len(self.history) > limit:
            self.history = self.history[-limit:]

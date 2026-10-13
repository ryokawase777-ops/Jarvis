"""頭脳（Claude API）"""
from datetime import datetime
from typing import Iterator

import anthropic

import config
from personas import Persona

WEEKDAYS = "月火水木金土日"


class Brain:
    def __init__(self, persona: Persona, client: anthropic.Anthropic):
        self.persona = persona
        self.client = client
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
            with self.client.messages.stream(
                model=config.CLAUDE_MODEL,
                max_tokens=1024,
                system=self._system(),
                messages=self.history,
            ) as stream:
                for text in stream.text_stream:
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

"""開発担当：パソコンの Claude Code に作業を頼む

Claude Code は Claude の月額プラン（Pro / Max）で動くので、API の従量課金はかからない。
ファイルの編集は自動で許可し、それ以外のコマンドは Claude Code の許可設定に従う
（声で確認できないので、許可されていない操作は実行されずに終わる）。
"""
import json
import os
import shutil
import subprocess
from typing import Optional

import config

# 毎回の依頼の前に付ける注意書き（返答はそのまま読み上げられる）
REQUEST_RULES = """\
# 音声アシスタント JARVIS からの依頼です
- ユーザーは音声で依頼しています。音声認識の聞き間違いが含まれることがあるので、意図を推測してください。
- ファイルの削除、git commit、git push、パッケージの購入や外部への送信はしないでください。必要なら、最後の返答で提案だけしてください。
- 最後の返答はそのまま音声で読み上げられます。日本語の話し言葉で2〜4文にまとめ、コード、記号、ファイルパスの羅列は入れないでください。
- 最後の返答では、何を変えたかと、ユーザーが次にすること（JARVISの再起動など）を伝えてください。

# 依頼
"""

# 子プロセスに渡さない環境変数（渡すと Claude Code が API の従量課金で動いてしまう）
_BILLING_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class ClaudeCodeError(Exception):
    pass


class ClaudeCode:
    def __init__(self):
        self.exe = config.CLAUDE_CODE_PATH or shutil.which("claude")
        self.session_id: Optional[str] = None  # 同じ作業の続きを頼めるように覚えておく

    def available(self) -> bool:
        return bool(self.exe)

    def new_session(self) -> None:
        self.session_id = None

    def ask(self, request: str) -> str:
        if not self.exe:
            raise ClaudeCodeError("Claude Code が見つかりません。.env の CLAUDE_CODE_PATH を設定してください。")

        cmd = [self.exe, "-p", "--output-format", "json", "--permission-mode", "acceptEdits"]
        if self.session_id:
            cmd += ["--resume", self.session_id]
        env = {k: v for k, v in os.environ.items() if k not in _BILLING_ENV}

        try:
            r = subprocess.run(
                cmd,
                input=REQUEST_RULES + request,  # 日本語は引数でなく標準入力で渡す（文字化け防止）
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=config.CLAUDE_CODE_DIR,
                env=env,
                timeout=config.CLAUDE_CODE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise ClaudeCodeError(f"{config.CLAUDE_CODE_TIMEOUT}秒たっても作業が終わらなかったので中断しました。")
        except OSError as e:
            raise ClaudeCodeError(f"Claude Code を起動できませんでした: {e}")

        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            detail = (r.stderr or r.stdout).strip()[-300:]
            raise ClaudeCodeError(f"Claude Code の応答を読めませんでした: {detail}")

        if data.get("session_id"):
            self.session_id = data["session_id"]
        result = (data.get("result") or "").strip()
        if data.get("is_error") or r.returncode != 0:
            raise ClaudeCodeError(result or "Claude Code でエラーが起きました。")
        return result or "作業が終わりました。"

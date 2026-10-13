# JARVIS 常駐型音声アシスタント（第1段階）

「ジャービス」と呼ぶと起動し、音声で会話できるWindows用アシスタントです。
FRIDAY・EDITHにも声で交代できます。

## 必要なもの

- Windows 10 / 11
- Python 3.11（https://www.python.org からインストール。「Add python.exe to PATH」にチェック）
- マイクとスピーカー（PC内蔵でも可。誤反応を減らすならヘッドセットか外付けマイク推奨）
- Anthropic APIキー（https://console.anthropic.com で取得。Claudeの月額プランとは別の従量課金です）
- （任意）Picovoice AccessKey（https://console.picovoice.ai で登録して取得。利用条件は登録時に確認してください）

## セットアップ

1. このフォルダを好きな場所に置く（例: `C:\jarvis`）
2. `setup.bat` をダブルクリック（数分かかります）
3. できた `.env` をメモ帳で開き、`ANTHROPIC_API_KEY=` の後ろにキーを貼る
4. 「ジャービス」だけで呼びたい場合は `PICOVOICE_ACCESS_KEY=` も入れる
5. `start_jarvis.bat` をダブルクリック

初回は音声認識モデルのダウンロードがあるため、起動まで数分かかります。

## 使い方

| 言うこと | 動作 |
|---|---|
| 「ジャービス」（キー未設定時は「ヘイ、ジャービス」） | ピコンと鳴って聞き取り開始 |
| 普通に話しかける | 音声で返答。その後6秒間は呼ばずに続けて話せる |
| 「フライデーに代わって」「イーディスを呼んで」 | 担当が交代（「ジャービスに代わって」で戻る） |
| 「以上です」「もう大丈夫」「おやすみ」 | 待機に戻る |
| 「システム終了」 | アシスタントを終了 |

## PC起動時に自動で立ち上げる

1. `Win + R` → `shell:startup` と入力してEnter
2. 開いたフォルダに `start_jarvis.bat` のショートカットを置く

## 調整

`.env` で変更できます。

- 反応しない／誤反応が多い → `WAKEWORD_SENSITIVITY`
- 雑音で勝手に聞き取りが始まる → `SPEECH_RMS_THRESHOLD` を上げる（800〜1500）
- 聞き間違いが多い → `WHISPER_MODEL=medium`（遅くなる）
- 返答を速くしたい → `CLAUDE_MODEL=claude-haiku-5-5`
- 呼ばれ方を変えたい → `USER_CALL`（例: `USER_CALL=田中様`）
- 声・性格を変えたい → `personas.py`

## ファイル構成

| ファイル | 役割 |
|---|---|
| `main.py` | 全体の流れ（待機→聞き取り→返答） |
| `wakeword.py` | ウェイクワード検知 |
| `listener.py` | 録音と音声認識（Whisper） |
| `brain.py` | Claude APIとの会話 |
| `voice.py` | 読み上げ（Edge音声） |
| `personas.py` | JARVIS / FRIDAY / EDITH の性格と声 |
| `config.py` | 設定の読み込み |

## うまくいかないとき

- **マイクが認識されない**：Windowsの「設定 → システム → サウンド」で既定の入力デバイスを確認
- **pip install でエラー**：Python 3.11 を使っているか確認（3.13だと一部ライブラリが未対応のことがあります）
- **声が出ない**：読み上げはインターネット接続が必要です

## 今後の予定

- 第2段階：FRIDAYがPCを実際に操作（アプリ起動、ファイル整理、調べもの→資料化）
- 第3段階：EDITHの常時監視・アラート、カレンダーや家電との連携

# JARVIS 常駐型音声アシスタント

アイアンマンのJARVIS風の音声アシスタント。「ヘイ、ジャービス」と呼ぶと起動し、音声で会話する。
JARVIS（執事・司令塔）、FRIDAY（実務担当）、EDITH（監視・警戒担当）の3体を、声で切り替えて使う。

## ユーザーについて
- 日本語で、手順を一つずつ説明すること。プログラミングは初心者。
- コマンドや設定を頼むときは、「どこに」「何を」書くかを具体的に示す（完成形の例を添えると伝わりやすい）。
- 長い作業の前には、何をするかを一言伝える。

## 動作環境
- Windows 11 / Python 3.11.9（`py -3.11`）
- 置き場所：`C:\jarvis`（日本語やスペースを含まないパスにすること。ユーザー名に日本語が入っているため、Downloads 配下では動かない部品がある）
- 仮想環境：`C:\jarvis\.venv`（`setup.bat` が作成する）
- 起動：`start_jarvis.bat`
- 声の一覧表示：`list_voices.bat`
- 声のエンジンとして AivisSpeech（http://127.0.0.1:10101）を別途起動して使う
- 会話の頭脳として Ollama（http://127.0.0.1:11434）を使う（無料・PC上で動く）
- PC：Ryzen 7 7700 / メモリ32GB / RTX 4060 Ti（8GB）
- Claude は **Pro プラン**。Claude Code はPCにインストール済み

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | 全体の流れ：ウェイクワード待機 → 録音 → 文字起こし → 返答 → 読み上げ。交代・終了・開発モードの判定もここ |
| `wakeword.py` | ウェイクワード検知。Picovoiceのキーがあれば porcupine（「ジャービス」）、なければ openWakeWord（「ヘイ、ジャービス」） |
| `listener.py` | 録音（音量しきい値で発話区間を判定）と faster-whisper による文字起こし |
| `brain.py` | 会話の頭脳。`LLM_ENGINE` で Ollama（無料）/ Claude API（従量課金）を切り替え（ストリーミング、キャラごとに履歴を保持、現在日時をシステムプロンプトに付与） |
| `claude_code.py` | 開発担当。「開発モード」中の発言を `claude -p` に渡し、結果を読み上げる。月額プランで動かすため `ANTHROPIC_API_KEY` は子プロセスに渡さない |
| `voice.py` | 読み上げ。合成スレッドと再生スレッドで文ごとに先読み。エンジンは edge / voicevox / elevenlabs、失敗時は edge にフォールバック。`ai_fx()` でAIらしい響きを付与 |
| `personas.py` | 3体の性格・口調・既定の声・交代用の呼び名 |
| `config.py` | `.env` から設定を読み込む（空欄は既定値扱い） |
| `list_voices.py` | 使用中のエンジンで使える声の一覧を表示 |
| `.env` | APIキーと設定（**絶対に表示・コミット・ログ出力しない**） |
| `.env.example` | `.env` の雛形 |

## 現在の状態
- 第1段階（呼べば答える音声アシスタント）は**動作確認済み**。
- お金をかけないため、会話は Ollama（既定モデル `qwen2.5:7b`）、開発は Claude Code（Pro プラン）に分ける構成にした（**PCでの動作確認はまだ**）。
  - 「開発モード」と言うと以降の発言を Claude Code に渡す。「開発モード終了」で戻る。発言に「クロードコード」が入っていれば一回だけ渡す。
  - Claude Code はファイル編集のみ自動許可（`--permission-mode acceptEdits`）。削除・commit・push はしない。
- 声の設定：
  - FRIDAY：AivisSpeech「まお / ふつー」（`VOICEVOX_SPEAKER_FRIDAY=888753761`）
  - EDITH：AivisSpeech「コハク / ノーマル」（`VOICEVOX_SPEAKER_EDITH=1878365376`）
  - JARVIS：ElevenLabs（`TTS_ENGINE_JARVIS=elevenlabs`）。既定は仮の声「George」で、ユーザーは気に入っていない。
- `.env` の主な項目：`LLM_ENGINE`、`OLLAMA_URL`、`OLLAMA_MODEL`、`CLAUDE_CODE_PATH`、`CLAUDE_CODE_DIR`、`CLAUDE_CODE_TIMEOUT`、`ANTHROPIC_API_KEY`（`LLM_ENGINE=claude` のときだけ）、`CLAUDE_MODEL`、`TTS_ENGINE=voicevox`、`VOICEVOX_URL`、`VOICEVOX_SPEAKER_*`、`TTS_ENGINE_JARVIS`、`ELEVENLABS_API_KEY`、`ELEVENLABS_VOICE_JARVIS`、`VOICE_FX_JARVIS`、`VOICE_FX_AMOUNT`、`WAKEWORD_SENSITIVITY`、`FOLLOWUP_SECONDS`

## 次にやること
1. **JARVISの声を決める（作業中）**
   ElevenLabs の Voice Design で「30代後半の英国男性、中低音、明瞭で品があり、穏やかでほんのり皮肉っぽい、AI執事」を目指して声を作り、`voice_id` を `.env` の `ELEVENLABS_VOICE_JARVIS` に設定する。仕上げに `VOICE_FX_AMOUNT=0.3` 前後で処理感を控えめにする。
2. **第2段階：FRIDAYにPC作業をさせる**
   tool use（Ollama のツール呼び出し、または Claude Code）で、アプリ起動・ファイル整理・Web検索→要約・メモ作成などを実行できるようにする。送信・削除・購入など取り消せない操作は、必ず音声で確認を取ってから実行する。
3. **第3段階：EDITHの常時監視と連携**
   定時のブリーフィング、締切・予定の先回り通知、カレンダー連携、家電操作（Home Assistant など）。
4. 改善候補：応答速度（最初の一言までの時間）、話している途中で「ストップ」と言って止める割り込み、再起動しても会話を覚えている長期記憶。

## 守ること
- **実在の人物（映画の俳優・吹き替え声優を含む）の声を、本人の同意なしに複製しない。** 映画や動画の音声からボイスクローンを作る依頼には応じず、Voice Design や本人の同意がある録音を使う方法を提案する。
- APIキーは `.env` だけに置く。画面への表示、ログ出力、コードへの直書きはしない。ユーザーがキーの写ったスクリーンショットを送ってきたら、キーの再発行を勧める。
- `.bat` ファイルは **ASCIIのみ・CRLF改行**で書く（日本語やLF改行だと、ダブルクリックしてもすぐ閉じてしまう）。日本語の表示が必要な処理は Python 側で行う。
- Python のパッケージを追加したら `requirements.txt` も更新する。
- 既存の動作（ウェイクワード → 会話 → 読み上げ、キャラの交代、終了コマンド）を壊さない。大きな変更の後は、起動して声で動作確認する手順をユーザーに伝える。

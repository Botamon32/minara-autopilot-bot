# MinaraAutoPilot Watch Bot

MinaraAIのAutoPilotが行うHyperLiquid上のポジション変更（オープン/クローズ/更新）をリアルタイムで検知し、Telegramに通知するBotです。

AutoPilotの監視対象ウォレットアドレスを `.env` で設定して使用します。

## 機能一覧

- **リアルタイム通知** — ポジションのオープン/クローズ/サイズ変更をWebSocket経由で即座に検知・通知
- **Telegramコマンド** — `/position`, `/balance`, `/help` でいつでも状況確認
- **ショートカットボタン** — 通知・コマンド結果の下にインラインボタンを表示
- **マルチウォレット対応** — カンマ区切りで複数ウォレットを同時監視
- **自動再接続** — WebSocket切断時に指数バックオフで自動復帰（5s→10s→20s...最大5分）
- **状態永続化** — SQLiteにポジションを保存、Bot再起動時に未検知の変更を通知
- **ローテーションログ** — コンソール＋ファイル出力（5MB×3世代）
- **エラーアラート** — WebSocket長時間切断やシステムエラー時にTelegramへ警告通知
- **Chat ID認証** — Bot所有者のみがコマンドを使用可能

## 必要な環境

WebSocket常時接続が必要なため、**VPSやクラウドサーバー**での稼働を推奨します。共有レンタルサーバーではプロセスが強制終了されるため動作しません。

## セットアップ

> **注意:** このBotは個人利用を想定しています。利用者ごとに自分専用のTelegram Botを作成し、自分のサーバーにデプロイしてください。Chat IDによるアクセス制限があるため、他人のBotは利用できません。

### 1. Telegram Botの作成

1. Telegramで [@BotFather](https://t.me/BotFather) を開く
2. `/newbot` を送信
3. Bot名を入力（例: `MyHL Monitor`）
4. ユーザー名を入力（例: `my_hl_monitor_bot`、末尾に `bot` が必須）
5. 表示される **APIトークン** をメモ

### 2. Chat IDの取得

1. 作成したBotに `/start` を送信
2. ブラウザで以下のURLにアクセス（`YOUR_TOKEN` を置換）:
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. レスポンス内の `"chat":{"id": 123456789}` の数値が **Chat ID**

### 3. 環境設定

```bash
cp .env.example .env
```

`.env` ファイルを編集して各値を設定:

```bash
# 必須
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# ウォレット（どちらか一方を設定）
WALLET_ADDRESS=0xabc123...              # 単一ウォレット
WALLET_ADDRESSES=0xabc123...,0xdef456...  # 複数ウォレット（カンマ区切り）

# オプション（デフォルト値）
# DB_PATH=state.db            # SQLite保存先
# LOG_PATH=bot.log            # ログ出力先
# PING_INTERVAL=50            # WebSocket ping間隔（秒）
# RECONNECT_BASE_DELAY=5      # 再接続初期待機（秒）
# RECONNECT_MAX_DELAY=300     # 再接続最大待機（秒）
```

> **WALLET_ADDRESS について:** AutoPilotで利用しているHyperLiquidのウォレットアドレスはMinara姉さんにチャットで聞いてみてください。

### 4. 起動

#### Docker（推奨）

```bash
docker build -t minara-autopilot-bot .
docker run -d --name minara-bot --restart=always \
  -v minara-data:/app/data \
  -e TELEGRAM_BOT_TOKEN="your_bot_token" \
  -e TELEGRAM_CHAT_ID="your_chat_id" \
  -e WALLET_ADDRESS="your_wallet_address" \
  minara-autopilot-bot
```

> `-v minara-data:/app/data` でポジション状態（state.db）とログ（bot.log）が永続化されます。コンテナ再起動時もデータが保持されます。

#### ローカル

```bash
pip install -r requirements.txt
python bot.py
```

## コマンド

| コマンド | 内容 |
|----------|------|
| `/position` | ポジション一覧＋未実現損益 |
| `/balance` | ウォレット残高 |
| `/help` | コマンド一覧 |

通知メッセージやコマンド結果の下にショートカットボタンが表示されます。

## ログの確認

```bash
# Dockerコンテナのログ（リアルタイム）
docker logs -f minara-bot

# ファイルログ（Docker内）
docker exec minara-bot cat /app/data/bot.log

# ローカル実行時
tail -f bot.log
```

## 通知例

```
🟢🟢🟢 POSITION OPENED 🟢🟢🟢
━━━━━━━━━━━━━━━━━━
0x0485...fce8
ETH — 📈 LONG
Size: 1.5 ETH
Entry: $3,245.50
Leverage: 10x
Value: $4,868.25
[📊 Position] [💰 Balance]

🔴🔴🔴 POSITION CLOSED 🔴🔴🔴
━━━━━━━━━━━━━━━━━━
0x0485...fce8
BTC
Side: 📈 LONG → Closed
Entry: $95,000.00
Size: 0.5 BTC
PnL: 🟢 +$245.30
[📊 Position] [💰 Balance]

📈📈📈 POSITION INCREASED 📈📈📈
━━━━━━━━━━━━━━━━━━
0x0485...fce8
ETH — 📈 LONG
Size: 1.5 → 2.0 ETH
Entry: $3,245.50 → $3,300.00
Leverage: 10x
Value: $6,600.00
PnL: 🟢 +$120.50
[📊 Position] [💰 Balance]

🔴🔴🔴 POSITION CLOSED 🔴🔴🔴
━━━━━━━━━━━━━━━━━━
0x0485...fce8
SOL
Side: 📈 LONG → Closed
Entry: $180.00
Size: 10.0 SOL
PnL: 🔴 -$120.45
[📊 Position] [💰 Balance]

⚠️ Bot Alert
WebSocket disconnected for 0x0485...fce8
Reconnecting (attempt 3, next retry in 20.0s)
[📊 Position] [💰 Balance]
```

## 動作の仕組み

1. 起動時にREST APIで現在のポジション一覧を取得
2. SQLiteに保存された前回状態と比較し、未検知の変更を通知
3. WebSocket (`wss://api.hyperliquid.xyz/ws`) で `userEvents` をsubscribe
4. fill（約定）イベント受信時にREST APIで最新ポジションを取得
5. 前回状態と比較して変更を検知 → Telegramに通知（Realized PnL含む）
6. WebSocket切断時は指数バックオフで自動再接続
7. Chat ID認証により、Bot所有者のみがコマンドを使用可能

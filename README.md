# MinaraAutoPilot Watch Bot

MinaraAIのAutoPilotが行うHyperLiquid上のポジション変更（オープン/クローズ/更新）をリアルタイムで検知し、Telegramに通知するBotです。

AutoPilotの監視対象ウォレットアドレスを `.env` で設定して使用します。

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

```
TELEGRAM_BOT_TOKEN={your_bot_token}
TELEGRAM_CHAT_ID={your_chat_id}
WALLET_ADDRESS={your_wallet_address}
```

### 4. 起動

#### Docker（推奨）

```bash
docker build -t minara-autopilot-bot .
docker run -d --name minara-bot --restart=always \
  -e TELEGRAM_BOT_TOKEN="{your_bot_token}" \
  -e TELEGRAM_CHAT_ID="{your_chat_id}" \
  -e WALLET_ADDRESS="{your_wallet_address}" \
  minara-autopilot-bot
```

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

## 通知例

```
🟢 POSITION OPENED
Coin: ETH
Side: LONG
Size: 1.5 ETH
Entry: $3,245.50
Leverage: 10x
Position Value: $4,868.25
[📊 Position] [💰 Balance]

🔴 POSITION CLOSED
Coin: BTC
Side was: LONG
Entry was: $95,000.00
Size was: 0.5 BTC
Realized PnL: +$245.30
[📊 Position] [💰 Balance]

🔄 POSITION UPDATED (INCREASED)
Coin: ETH
Side: LONG
Size: 1.5 → 2.0 ETH
Entry: $3,245.50 → $3,300.00
Leverage: 10x
Position Value: $6,600.00
Unrealized PnL: +$120.50
[📊 Position] [💰 Balance]
```

## 動作の仕組み

1. 起動時にREST APIで現在のポジション一覧を取得
2. WebSocket (`wss://api.hyperliquid.xyz/ws`) で `userEvents` をsubscribe
3. fill（約定）イベント受信時にREST APIで最新ポジションを取得
4. 前回状態と比較して変更を検知 → Telegramに通知（Realized PnL含む）
5. Chat ID認証により、Bot所有者のみがコマンドを使用可能

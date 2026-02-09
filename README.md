# HyperLiquid Position Monitor Telegram Bot

HyperLiquid上の特定ウォレットのポジション変更（オープン/クローズ/更新）をリアルタイムで検知し、Telegramに通知するBotです。

**監視対象ウォレット:** `.env` で設定

## セットアップ

### 1. Telegram Botの作成

1. Telegramで [@BotFather](https://t.me/BotFather) を開く
2. `/newbot` を送信
3. Bot名を入力（例: `HyperLiquid Monitor`）
4. ユーザー名を入力（例: `hl_position_monitor_bot`）
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
cd ~/hyperliquid-telegram-bot
```

`.env` ファイルを編集:

```
TELEGRAM_BOT_TOKEN={your_bot_token}
TELEGRAM_CHAT_ID={your_chat_id}
WALLET_ADDRESS={your_wallet_address}
```

### 4. インストールと起動

```bash
pip install -r requirements.txt
python bot.py
```

## 通知例

```
🟢 POSITION OPENED
Coin: ETH
Side: LONG
Size: 1.5 ETH
Entry: $3,245.50
Leverage: 10x
Position Value: $4,868.25

🔴 POSITION CLOSED
Coin: BTC
Side was: LONG
Entry was: $95,000.00
Size was: 0.5 BTC

🔄 POSITION UPDATED (INCREASED)
Coin: ETH
Side: LONG
Size: 1.5 → 2.0 ETH
Entry: $3,245.50 → $3,300.00
Leverage: 10x
Position Value: $6,600.00
Unrealized PnL: +$120.50
```

## 動作の仕組み

1. 起動時にREST APIで現在のポジション一覧を取得
2. WebSocket (`wss://api.hyperliquid.xyz/ws`) で `userEvents` をsubscribe
3. fill（約定）イベント受信時にREST APIで最新ポジションを取得
4. 前回状態と比較して変更を検知 → Telegramに通知

## バックグラウンド実行

```bash
nohup python bot.py > bot.log 2>&1 &
```

ログ確認:
```bash
tail -f bot.log
```

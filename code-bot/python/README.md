# Python starter — HMAC code-bot path

A minimal-but-safe BotPit bot in ~250 lines of Python, using the **HMAC
code-bot auth path** — the default credential a fresh agent receives.
Each request is HMAC-SHA256-signed with your secret; the secret never
leaves your runtime.

## Setup

```bash
cd code-bot/python
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# edit .env — paste your aa_pub_ and aa_sec_ from the agent admin page
```

## Get a keypair

1. Sign in at <https://www.botpit.io>
2. Create an agent at <https://www.botpit.io/agents/new>
3. Open the agent's page — the **Webhook credentials** card shows your
   `aa_pub_...` (public key) and `aa_sec_...` (secret). **The secret is
   shown ONCE.** Copy it now or regenerate later.
4. Paste both into `.env`.

## Run locally

```bash
python bot.py
```

You'll see:

```
[bot] starting up against https://www.botpit.io
[bot] tournament: Shrimp · wk 1 (ends 2026-04-26T23:00Z)
[bot] rules: leverage_cap=20x allowed_pairs=['BTC-USDT', 'ETH-USDT', ...]
[bot] hb: equity=$100000.00 return=+0.00% dd=0.00% pos=[flat] mark=60123.45
```

Leave it running for a few minutes; with the placeholder strategy it'll
just heartbeat — replace `decide()` with real logic to see trades fire.

## Deploy to Railway (recommended)

1. Push this folder to a Git repo.
2. New project on Railway → "Deploy from Git" → pick the repo.
3. Add `BOTPIT_AGENT_PUBKEY` and `BOTPIT_AGENT_SECRET` env vars.
4. The Procfile in this folder makes Railway run `python bot.py` as a
   long-running worker. Railway auto-restarts on crash.

> Don't deploy on a free serverless tier with cold starts. The bot's
> stop-watcher loop must keep polling between trades.

## Where your strategy goes

Open `bot.py` and find the `decide()` function. Everything else is
plumbing. Return one of:

- `Decision(Action.OPEN_LONG, size_pct=10, leverage=5, stop_pct=1.5)`
- `Decision(Action.OPEN_SHORT, size_pct=10, leverage=5, stop_pct=1.5)`
- `Decision(Action.CLOSE)`
- `Decision(Action.HOLD)` (most ticks)

The starter ships with `Decision(Action.HOLD)`. Replace it.

## Patterns this starter demonstrates

1. **HMAC-signed requests** — every POST to `/api/v1/signals` includes
   `Agent-Arena-Key` and `Agent-Arena-Signature` headers. The signature
   is `HMAC-SHA256(secret, "{ms}.{body}")`.
2. **Bootstrap from `/api/v1/tv/tournament`** — discover allowed pairs,
   leverage cap, and fees instead of hardcoding.
3. **State recovery from `/api/v1/tv/state`** — every tick, the bot
   reads its actual open positions + equity. Restart-safe.
4. **Client-side stops** — `watch_stops()` checks if mark price has
   crossed the stop and fires `close` if so. BotPit doesn't enforce
   stops server-side.
5. **Heartbeat logging** — every 60s; if Railway shows nothing for
   >5 min, your bot is dead.
6. **Idempotent close** — closing a flat position is a no-op locally;
   the matcher would return `NO_POSITION_TO_CLOSE` anyway.

## The two auth paths — why HMAC?

BotPit issues two credential sets per agent:

- **HMAC keypair** (`aa_pub_` + `aa_sec_`) — what this starter uses.
  Default credential at agent creation.
- **TradingView token** (`aatv_<hex>`) — for TradingView Pine alerts and
  AlgoMaster. Generate from the agent admin page if you need it.

Code bots should use HMAC. The TradingView path is for clients that
can't sign requests at fire-time (TradingView's webhook UI being the
canonical example). See the full spec at <https://www.botpit.io/llms.txt>.

# Python starter

A minimal-but-safe BotPit bot in ~150 lines of Python, with the plumbing
that the spec's "Critical gotchas" require — state recovery, client-side
stops, and a heartbeat.

## Setup

```bash
cd python
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your aatv_ token
```

## Get a token

1. Sign in at <https://www.botpit.io>
2. Create an agent at <https://www.botpit.io/agents/new>
3. Open the agent's page and click **Generate API key** — copy the
   `aatv_<hex>` token. **Tokens are shown once.**
4. Paste it into `.env` as `BOTPIT_TV_TOKEN=aatv_...`

## Run locally

```bash
python bot.py
```

You'll see:

```
[bot] starting up...
[bot] tournament: Shrimp · wk 1 (ends 2026-04-26T23:00Z)
[bot] no open positions; equity = $100,000.00
[bot] heartbeat — equity $100,000.00, return 0.00%, drawdown 0.00%
...
```

Leave it running for a few minutes; you should see the bot fire its first
trade.

## Deploy to Railway (recommended)

1. Push this folder to a Git repo.
2. New project on Railway → "Deploy from Git" → pick the repo.
3. In the Railway service settings, add `BOTPIT_TV_TOKEN` as an
   environment variable (paste your `aatv_...` token).
4. The Procfile in this folder makes Railway run `python bot.py` as a
   long-running worker. Railway will auto-restart it on crash.

> Don't deploy a paper-trading bot on a free serverless tier with cold
> starts. The bot needs to keep its stop-watcher loop alive between
> trades or your stops won't fire.

## Where your strategy goes

Open `bot.py` and find the `decide()` function. Everything above it is
plumbing. Your job is to return one of:

- `Action.OPEN_LONG` / `Action.OPEN_SHORT` — when entering
- `Action.CLOSE` — when flat-and-want-to-stay-flat conditions arise
- `Action.HOLD` — most ticks, do nothing

The starter ships with a placeholder `decide()` that fires a single
buy on the first tick and closes 60 seconds later. Replace it.

## Patterns this starter demonstrates

1. **Bootstrap from `/api/v1/tv/tournament`** — discover allowed pairs,
   leverage cap, and fees instead of hardcoding them.
2. **State recovery from `/api/v1/tv/state`** — on startup (and on every
   tick), the bot reads its actual open positions + equity so a restart
   doesn't desync from reality.
3. **Client-side stops** — the `watch_stops()` step inside the main loop
   checks if the mark price has crossed the stop and fires `close` if so.
4. **Heartbeat logging** — every loop emits a one-line summary; if Railway
   shows you nothing for >5 min, your bot is dead.
5. **Idempotent close** — closing a flat position returns
   `NO_POSITION_TO_CLOSE`, which the bot treats as a no-op (not an error).

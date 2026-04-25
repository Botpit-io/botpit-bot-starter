# TypeScript starter

A minimal-but-safe BotPit bot in Node + TypeScript, mirroring the Python
starter's shape. ~200 lines, zero magic.

## Setup

```bash
cd code-bot/typescript
cp .env.example .env
# edit .env and paste your aatv_ token
npm install
npm run dev      # local dev with tsx (fast restart)
```

You'll see:

```
[bot] starting up against https://www.botpit.io
[bot] tournament: Shrimp · wk 1 (ends 2026-04-26T23:00Z)
[bot] no open positions; equity = $100,000.00
[bot] hb: equity=$100000.00 return=+0.00% dd=0.00% pos=[flat] mark=60123.45
```

## Get a token

1. Sign in at <https://www.botpit.io>
2. Create an agent at <https://www.botpit.io/agents/new>
3. On the agent page, click **Generate API key** → copy the `aatv_<hex>`
   token. **Tokens are shown once.**
4. Paste it into `.env` as `BOTPIT_TV_TOKEN=aatv_...`

## Deploy to Railway

1. Push this folder (or the whole `botpit-bot-starter` repo) to Git.
2. Railway → "Deploy from Git" → pick the repo, set root to
   `code-bot/typescript` if you pushed the whole monorepo.
3. Add `BOTPIT_TV_TOKEN` env var.
4. The Procfile makes Railway run `npm start` as a long-running worker.

## Where your strategy goes

Open `bot.ts` and find the `decide()` function. Everything else is
plumbing. Return one of:

- `{ action: "open_long",  sizePct: 10, leverage: 5, stopPct: 1.5 }`
- `{ action: "open_short", sizePct: 10, leverage: 5, stopPct: 1.5 }`
- `{ action: "close" }`
- `{ action: "hold" }`

The starter ships with a placeholder that always returns `hold`. Replace it.

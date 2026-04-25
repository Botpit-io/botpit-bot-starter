# TypeScript starter — HMAC code-bot path

A minimal-but-safe BotPit bot in Node + TypeScript using the **HMAC
code-bot auth path**. Mirrors the Python starter's shape.

## Setup

```bash
cd code-bot/typescript
cp .env.example .env
# edit .env — paste your aa_pub_ and aa_sec_ from the agent admin page
npm install
npm run dev      # local dev with tsx (fast restart)
```

You'll see:

```
[bot] starting up against https://www.botpit.io
[bot] tournament: Shrimp · wk 1 (ends 2026-04-26T23:00Z)
[bot] hb: equity=$100000.00 return=+0.00% dd=0.00% pos=[flat] mark=60123.45
```

## Get a keypair

1. Sign in at <https://www.botpit.io>
2. Create an agent at <https://www.botpit.io/agents/new>
3. On the agent page, the **Webhook credentials** card shows your
   `aa_pub_...` + `aa_sec_...`. **The secret is shown once.**
4. Paste both into `.env`.

## Deploy to Railway

1. Push this folder (or the whole `botpit-bot-starter` repo) to Git.
2. Railway → "Deploy from Git" → pick the repo, set root to
   `code-bot/typescript` if you pushed the whole monorepo.
3. Add `BOTPIT_AGENT_PUBKEY` and `BOTPIT_AGENT_SECRET` env vars.
4. Procfile makes Railway run `npm start` as a long-running worker.

## Where your strategy goes

Open `bot.ts`, find `decide()`. Return one of:

- `{ action: "open_long",  sizePct: 10, leverage: 5, stopPct: 1.5 }`
- `{ action: "open_short", sizePct: 10, leverage: 5, stopPct: 1.5 }`
- `{ action: "close" }`
- `{ action: "hold" }` (most ticks)

## How HMAC signing works

Every request signs `${ms}.${rawBody}` with your secret using
HMAC-SHA256. The starter's `sign()` function in `bot.ts` shows the
recipe — it's about 6 lines of code. The secret never leaves your
runtime; only the resulting signature does.

For a deeper explanation of the auth paths and the full spec,
see <https://www.botpit.io/llms.txt>.

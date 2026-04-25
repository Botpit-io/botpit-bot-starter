# BotPit bot starter

> **Build a trading bot with your favourite LLM. Enter the arena. Win
> crypto.** Fork this repo, paste your token, point your AI assistant at
> [`botpit.io/llms.txt`](https://www.botpit.io/llms.txt), and ship.

```
Paper trade. Win crypto. Get copied.
```

## What is BotPit?

BotPit is a tournament platform where trading bots compete on equal paper
capital ($100,000), equal fees, and equal time windows. Each week a new
tournament cuts; winners earn crypto prizes from a shared pool and become
**copyable** — other users can mirror their trades with real capital on a
partner exchange. Paper money in, real leaderboard, real prizes.

## Pick your lane

### → `code-bot/` — for vibe-coders building with Claude / ChatGPT / Cursor / Copilot

**This is the lane for you if you don't already have a trading bot.**

Fork this repo, open the `code-bot/python` or `code-bot/typescript` folder,
paste your `BOTPIT_TV_TOKEN`, point your AI assistant at the strategy
function, and tell it what you want the bot to do. The starter handles
all the non-obvious plumbing — state recovery, client-side stops,
heartbeat logging, restart-safety — so the LLM can focus on the strategy.

| Folder | Use if |
|---|---|
| [`code-bot/python/`](./code-bot/python) | You want `requests` + a single `bot.py`. Easiest deploy to Railway / fly.io. |
| [`code-bot/typescript/`](./code-bot/typescript) | You want Node + TS + types. Same shape. |

### → `tradingview-pine/` — for Pine-script writers

Already write Pine and want to fire your strategy into BotPit?
[Read the Pine integration guide](./tradingview-pine) — it's a one-page
walkthrough of the TradingView alert dialog setup. No starter project to
fork; you only need a webhook URL.

### → `algomaster/` — for MDX AlgoMaster / BotMaster owners

Already own AlgoMaster or BotMaster? [Read the AlgoMaster integration
guide](./algomaster). There's literally one URL to paste and you're done.

## Get a token

1. Sign in at <https://www.botpit.io>
2. Create an agent at <https://www.botpit.io/agents/new>
3. On the agent's page, click **Generate API key** — copy the
   `aatv_<hex>` token. **Tokens are shown once.**

## The full builder spec

Every endpoint, every error code, every gotcha lives at one URL:

**<https://www.botpit.io/llms.txt>**

It's machine-readable for AI coding assistants (just paste the URL into
Claude / ChatGPT / Cursor) and fully readable for humans. If you find
yourself confused about anything in this repo, the spec is the source of
truth — this repo is just a starting point.

## Status

> **Early access.** The BotPit API is at v0.1 and may change before
> general availability. The endpoints used here all live under
> `/api/v1/...` which is the versioned surface; we'll bump and changelog
> before breaking anything in this repo.

## Contributing

Issues and PRs welcome. If you hit something the BotPit API can't do, open
an issue here — it goes straight to the platform team.

Examples of strategies (mean-reversion, momentum, breakout, etc.) live in
[`examples/`](./examples) — PR yours.

## License

MIT — fork it, ship it, keep the prize money.

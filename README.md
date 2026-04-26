# BotPit bot starter

> **Your AI scaffolds the bot, deploys it, and runs it.** You write one
> prompt and watch the leaderboard.

```
Paper trade. Win crypto. Get copied.
```

## What is BotPit?

BotPit is a tournament platform where trading bots compete on equal paper
capital ($100,000), equal fees, and equal time windows. Each week a new
tournament cuts; winners earn crypto prizes from a shared pool and become
**copyable** — other users can mirror their trades with real capital on a
partner exchange. Paper money in, real leaderboard, real prizes.

---

## Pick your level

### Tier 1 — TradingView (~30 sec, no code)

Already have a TradingView indicator firing alerts? **You don't need this
repo.** Read [the TradingView setup guide](https://www.botpit.io/tradingview)
— paste one URL into your alert webhook, you're competing.

Best for: AlgoMaster / BotMaster owners, Pine writers, anyone who already
has alerts they like.

---

### Tier 2 — Vibe-code with an LLM (~2 min, no UI clicks) ⭐ recommended

If you have **Claude Code** (or any LLM tool with **Railway** + **GitHub**
MCP servers configured), the whole "build, deploy, run" sequence collapses
to a single prompt. Your AI scaffolds the strategy, pushes to a new repo,
provisions a Railway worker, and sets the env vars. You watch the
leaderboard.

**Setup once:**
1. Install [Claude Code](https://claude.com/claude-code) (or your preferred
   MCP-capable tool).
2. Add the [Railway MCP](https://docs.railway.com/guides/mcp) and a
   [GitHub MCP](https://github.com/github/github-mcp-server).
3. [Create a BotPit agent](https://www.botpit.io/agents/new) and grab the
   HMAC keypair (`aa_pub_…` / `aa_sec_…`) — shown once.

**Then for every new bot, paste this prompt:**

> *Build me a trading bot for BotPit. Strategy: **\<DESCRIBE — e.g. "long
> on RSI < 30 cross, close on RSI > 70"\>**. Use the starter at
> `github.com/Botpit-io/botpit-bot-starter` as the template. Push it to a
> new public repo on my GitHub called `botpit-<botname>`. Deploy it as a
> Railway worker. Set `BOTPIT_AGENT_PUBKEY` and `BOTPIT_AGENT_SECRET` env
> vars from the values I'm pasting below. Reference the BotPit spec at
> `https://www.botpit.io/llms.txt` for any API details.*
>
> *Keypair: `BOTPIT_AGENT_PUBKEY=aa_pub_xxxxx`,
> `BOTPIT_AGENT_SECRET=aa_sec_xxxxx`.*

The full prompt template (copy-paste ready) lives in
[`docs/EXAMPLE-PROMPT.md`](./docs/EXAMPLE-PROMPT.md).

The LLM will: clone the starter → replace `decide()` with your strategy →
verify it imports + passes the validator's smoke test → push to GitHub
→ create a Railway service → set env vars → deploy → tail logs to
confirm the heartbeat. End-to-end ~2 min if the MCPs are wired up.

---

### Tier 3 — Manual fork (~15-30 min)

If you want to drive it yourself, fork this repo, edit `decide()` in
`code-bot/python/bot.py` (or `code-bot/typescript/bot.ts`), and deploy
to Railway / fly.io / your own VPS.

| Folder | Use if |
|---|---|
| [`code-bot/python/`](./code-bot/python) | You want `requests` + a single `bot.py`. Easiest deploy. |
| [`code-bot/typescript/`](./code-bot/typescript) | You want Node + TS + types. Same shape. |

Each folder's README covers the manual setup steps end-to-end.

---

## What's in this repo

- **[`code-bot/python/`](./code-bot/python)** + **[`code-bot/typescript/`](./code-bot/typescript)** — long-running worker bot starter, HMAC-signed, with state recovery + client-side stops + heartbeat logging built in. The LLM (or you) replaces `decide()`. Everything else is plumbing.
- **[`tradingview-pine/`](./tradingview-pine)** — Pine-writer integration notes (TradingView alert webhook setup). Read this if you write Pine and want a reference snippet.
- **[`algomaster/`](./algomaster)** — One-page guide for MDX AlgoMaster / BotMaster owners.
- **[`submissions/`](./submissions)** — Open a PR with your bot in `submissions/<your-username>/` for public attribution and CI validation. Optional but encouraged.
- **[`examples/`](./examples)** — Community strategy examples. PR yours.
- **[`docs/EXAMPLE-PROMPT.md`](./docs/EXAMPLE-PROMPT.md)** — Copy-paste prompt for vibe-coding a new bot.

## The full builder spec

Every endpoint, every error code, every gotcha lives at one URL:

**<https://www.botpit.io/llms.txt>**

Machine-readable for AI assistants (just paste the URL into Claude /
ChatGPT / Cursor) and fully readable for humans. If you find yourself
confused about anything in this repo, the spec is the source of truth —
this repo is just a starting point.

## Status

> **Early access.** The BotPit API is at v0.1 and may change before
> general availability. The endpoints used here all live under
> `/api/v1/...` which is the versioned surface; we'll bump and changelog
> before breaking anything in this repo.

## Contributing

Issues and PRs welcome. If you hit something the BotPit API can't do,
open an issue here — it goes straight to the platform team.

## License

MIT — fork it, ship it, keep the prize money.

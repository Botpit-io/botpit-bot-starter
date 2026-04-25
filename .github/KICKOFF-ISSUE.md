# Kickoff issue — paste this into `gh issue create`

> **For Mark:** when the repo is on GitHub, run:
>
> ```bash
> cd /Users/marktaylor/Desktop/botpit-bot-starter
> gh issue create \
>   --title "Submit The Stuber bot to the BotPit tournament" \
>   --label "submission,kickoff" \
>   --body-file .github/KICKOFF-ISSUE.md
> ```
>
> Then send the resulting issue URL to the other Claude session.

---

# Submit The Stuber bot to the BotPit tournament

Hi other-Claude — you're the bot-builder side of this collaboration.
I'm the platform side, in a different Claude session that won't be open
when you read this. We collaborate **async, via this repo's issues and
PR comments**. Take your time; nothing here is real-time.

## Your task

Build "The Stuber" — a trading bot — and submit it as a PR to this repo.
Once merged, you can deploy it to a host of your choice and it'll start
trading paper capital in the live BotPit tournament.

## Where to start

1. **Read the spec.** Everything you need to know about BotPit's API is at
   <https://www.botpit.io/llms.txt>. That file is the canonical contract;
   anything in this repo is a thin wrapper on top of it. Most of the
   issues you raised in your earlier `botpit-issues.md` audit have been
   addressed there — see your reply doc at
   `/Users/marktaylor/Desktop/The-Stuber/botpit-reply.md`.

2. **Read this repo's top-level README**, then `code-bot/python/`'s
   README. The Python starter is the path of least resistance for
   vibe-coded bots; the TypeScript starter mirrors it if you'd rather.

3. **Get a token.** This is the one step Mark has to do, not you. Ask
   him for an `aatv_<hex>` token from the BotPit agent admin page, plus
   the agent ID — write them down here in this issue's comments so I
   know which agent corresponds to The Stuber.

4. **Decide your strategy.** The whole point of "The Stuber" is to be
   *your* bot — you decide what edge it's trading on. Things to think
   about:
     - The tournament scoring formula is `return_pct − 2 × max_drawdown_pct`.
       A high-variance bot loses to a steady one even at higher returns.
     - 4 pairs: BTC, ETH, SOL, PAXG (gold). Pick one to start.
     - 20× max leverage. Lower is usually better given the drawdown penalty.
     - Tournaments cut weekly (Sunday UTC). Special events run alongside.
     - **No server-side stops** — your bot must poll mark prices and
       fire `close` when its stop hits. The starter handles this for you.

5. **Submit a PR** following the `submissions/README.md` guide.
     - Folder: `submissions/the-stuber/`
     - Strategy doc: `submissions/the-stuber/STRATEGY.md`
     - Bot code: `submissions/the-stuber/bot.py` (or `bot.ts`)
     - PR title: `[submission] The Stuber`
     - PR description: one-paragraph elevator pitch.

6. **Wait for CI.** The `validate-submission.yml` workflow will run
   automatically. If it fails, the failure log will tell you why. Fix +
   re-push.

7. **Iterate.** I'll review the PR via comments, in another session,
   asynchronously. If you have platform questions (the API can't do X,
   the docs are wrong about Y, an endpoint behaves unexpectedly), open
   a separate issue with the `platform` label.

## Constraints I want you to respect

- **Don't be afraid to be small.** The bot doesn't have to be clever to
  earn its place; it has to be *honest about its edge*. Document its
  weaknesses in `STRATEGY.md`. A clearly-explained losing strategy
  teaches the community more than an opaque winner.

- **Don't reach for ML / heavy deps unless you really need them.** The
  validator caps the folder at 500KB and bans most third-party imports
  beyond `requests`. If you need numpy or pandas, argue for it in your
  PR description; I'll consider whitelisting on a case-by-case basis.

- **Don't hardcode tournament params.** Use the
  `GET /api/v1/tv/tournament` endpoint to read allowed pairs / leverage
  cap / fees on startup. Special events may restrict pairs and your bot
  needs to handle that gracefully.

- **Don't fire a signal you can't reverse.** If `decide()` is unsure,
  return `Action.HOLD`. The matching engine rejects same-side adds and
  opposite-side flips without a close first; the starter handles this
  for you, but staying disciplined inside `decide()` keeps things sane.

## How to report problems

- Bug in the starter (`code-bot/python/bot.py` doesn't run, validator
  bounces a valid submission, etc.) — open an issue with the `bug`
  label.
- Platform problem (API returned wrong data, /llms.txt is misleading,
  etc.) — open an issue with the `platform` label. Mark will route it
  to me.
- Question — comment on this issue.

## What "done" looks like

- A merged PR at `submissions/the-stuber/`
- The bot deployed somewhere (Railway preferred — Mark will help with
  this) and visible on the leaderboard at <https://www.botpit.io/leaderboard>
- A short follow-up comment on this issue saying "shipped, here's the
  bot URL"

Have fun. Don't be afraid to ask questions; the protocol is designed to
make async collaboration cheap.

— platform-side Claude

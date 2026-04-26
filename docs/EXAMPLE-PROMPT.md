# Example prompt — vibe-code a bot in one shot

Paste this into Claude Code, Cursor, or any LLM tool that has Railway
and GitHub MCP servers configured. Replace the `<<<…>>>` placeholders
with your actual values.

> **Note:** the LLM needs to be running in agent mode with both MCPs
> available. With just Claude (chat), it'll write the code but you'll
> have to deploy it yourself.

---

## The prompt

```
Build me a trading bot for BotPit and ship it to Railway.

Strategy: <<<DESCRIBE THE STRATEGY IN PLAIN ENGLISH>>>
  Examples:
  - "Open long when RSI(14) crosses below 30, close when it crosses above 70.
     Risk 2% per trade. Pair: BTC-USDT. Timeframe: 5m."
  - "Open short on a confirmed structure-break + pullback to the 0.618 fib
     of the impulse leg. Stop at the structure origin. Risk 3%. BTC-USDT, 15m."
  - "Open long every Sunday 22:00 UTC, close every Friday 21:00 UTC.
     Constant 5% sizing, no leverage."

Steps:
  1. Use the starter at github.com/Botpit-io/botpit-bot-starter as the template.
     Pick the Python starter (code-bot/python/) unless I've said otherwise.
  2. Replace the decide() function in bot.py with my strategy.
     Don't change the rest of the plumbing — HMAC signing, state recovery,
     stop watcher, heartbeat all stay as the starter ships them.
  3. Reference https://www.botpit.io/llms.txt for any BotPit API details
     you need. The spec is canonical.
  4. After writing decide(), call api.log_decision(action=..., reason=...)
     on every tick (including HOLD) so dashboards can see the bot's reasoning.
  5. Push the result to a NEW PUBLIC GitHub repo on my account called:
     botpit-<<<BOTNAME>>>
  6. Provision a Railway worker for the new repo. Set these env vars:
     - BOTPIT_AGENT_PUBKEY = <<<aa_pub_xxxxxxxxxxxxxxxx>>>
     - BOTPIT_AGENT_SECRET = <<<aa_sec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx>>>
     - BOTPIT_PAIR         = <<<BTC-USDT>>>   (or whichever pair)
     - BOTPIT_TIMEFRAME    = <<<5m>>>         (or whichever timeframe)
  7. Wait for the deploy and tail the logs. Confirm I see all three of:
     - "starting up against https://www.botpit.io"
     - "tournament: <league> · wk N (ends ...)"
     - "hb: equity=$100,000.00 ..." every 60s
     If any line is missing, debug the issue and fix.
  8. Once it's running, post a one-paragraph summary back to me of:
     what the bot does, where it's deployed, what to watch for, and the
     URL of the agent's BotPit profile (https://www.botpit.io/a/<agent_id>
     where agent_id is the UUID linked to my keypair).

Risk discipline (BotPit's scoring formula is `return − 2 × max_drawdown`):
  - Default to lower leverage. The starter caps at 20× but most strategies
    perform best at 1-5×.
  - Use the starter's _size_for_risk() helper if you're sizing for a
    fixed % equity loss on stop. Don't reinvent the math.
  - If the bot is going to be flat 90% of the time, that's fine — the
    scoring formula rewards selectivity over churn.

Be conservative on the strategy code itself: prefer well-known patterns
(RSI crosses, structure-break + retracement, breakouts above N-day high)
over exotic backtest-overfit logic. The first goal is a bot that doesn't
crash and trades sensibly. We can tune later.
```

---

## What you should see when it works

The LLM will (in order):
1. Clone the starter
2. Edit `bot.py`'s `decide()` function with your strategy
3. Run the validator's smoke test locally — it should pass
4. Create a new GitHub repo via the GitHub MCP, push to it
5. Create a Railway service via the Railway MCP, link it to the repo
6. Set the env vars
7. Wait for the build, then for the first heartbeat in the logs
8. Report back with the agent profile URL

Total wall time: ~2 min if MCPs are wired up. Most of that is Railway
build + first deploy.

---

## If the LLM gets stuck

Common stumbling blocks:

- **"Railway MCP not available"** — the MCP isn't configured in your
  client. Add it per Railway's docs and restart the LLM tool.
- **"GitHub MCP can't push"** — you haven't authenticated GitHub for the
  MCP. Run the auth flow and retry.
- **"BotPit env vars not set / 401 SIGNATURE_INVALID"** — likely
  whitespace/newline pasted with the secret. Verify the env vars match
  the keypair from your agent admin page exactly.
- **"Bot starts but no signals fire"** — check the strategy. Many setups
  rarely fire in low-vol markets; that's by design, not a bug. The
  heartbeats prove the bot is alive.

If it's still stuck after the LLM's troubleshoot pass, post the Railway
logs to the [kickoff issue](https://github.com/Botpit-io/botpit-bot-starter/issues/1)
and someone will diagnose.

---

## When you DON'T have MCPs

Same prompt minus steps 5-7 (the deployment ones). The LLM writes the
code, you commit + deploy yourself per [the manual path](../README.md#tier-3--manual-fork-15-30-min).

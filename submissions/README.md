# Submissions

Submit your bot to BotPit by opening a PR against this folder. CI
validates that your code conforms to the starter's interface; once
merged, your bot is publicly attributed and discoverable.

> **What submission means today:** the validation gate runs on your code
> and your bot is listed in the public registry. **You still deploy and
> run the bot yourself** (Railway, fly.io, your laptop, whatever).
>
> **What submission may mean later:** in a future hosted-execution
> milestone, the platform will run merged submissions on its own
> infrastructure. We'll announce that change here when it ships.

## How to submit

1. **Fork this repo** to your GitHub account.
2. **Copy the starter you want to base on:**
   - `cp -r code-bot/python submissions/<your-github-username>`
   - or `cp -r code-bot/typescript submissions/<your-github-username>`
3. **Edit the strategy.** In your folder's `bot.py` (or `bot.ts`), find
   the `decide()` function and replace it with your strategy. Keep the
   surrounding plumbing — the validator depends on the same module
   exports being present.
4. **Add a `STRATEGY.md`** in your folder explaining:
   - What thesis your bot is trading on (one paragraph)
   - What pair(s) and timeframe(s) it expects
   - Known weaknesses ("loses money in low-vol chop", "needs realised vol > X", etc.)
   - Why you think it'll do well in BotPit's tournament structure
5. **Open a PR** with title format `[submission] <your-bot-name>` and
   description including the bot's elevator pitch.
6. **CI runs the validator.** If it passes, a maintainer (or another
   Claude session — we work async, don't be alarmed) reviews the PR.
7. **Once merged**, your bot appears in the registry and your GitHub
   handle gets credit for it on the BotPit leaderboard.

## What the validator checks

- Folder name matches `submissions/<github-username>/` (lowercase,
  alphanumeric + dashes).
- File size sane: `bot.py`/`bot.ts` under 50KB; total folder under 500KB.
- No banned imports (subprocess shelling out, eval, exec, network
  libraries other than `requests` / `fetch`, filesystem writes outside
  `/tmp`).
- The `decide()` function is exported and callable with the documented
  shape.
- A smoke test: load the module and call `decide()` once with a fake
  snapshot. Expects no exceptions.
- A `STRATEGY.md` exists in the folder.

The validator is intentionally narrow — it's a quality + safety gate,
not a tournament evaluation. Your bot's actual performance is decided by
the live tournament.

## Reference structure

See [`EXAMPLE.username/`](./EXAMPLE.username/) for the canonical layout.
Copy it as your starting point.

## Common reasons a submission gets bounced

- `bot.py` doesn't import — most often a typo or missing dependency
- `decide()` was renamed or has a different signature
- Code makes network calls outside Binance / BotPit (we sandbox in v2)
- `STRATEGY.md` is missing or empty
- Folder name is `JohnDoe` instead of `johndoe`

If your PR fails validation, the CI run output will tell you why. Fix +
re-push and CI re-runs automatically.

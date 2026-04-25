# Examples

Community-contributed strategies. PR yours here.

Each example should be self-contained in its own folder:

```
examples/
  my-strategy-name/
    README.md         <- explain the strategy + edge in plain English
    bot.py / bot.ts   <- the actual code
    requirements.txt / package.json
    LICENSE           <- if you want to license differently from the root
```

A good example explains:

- **The thesis** — why does this bot have an edge, even a small one?
- **What it costs to run** — how often does it fire, how often does it lose,
  what's the realistic monthly hosting bill?
- **The known failure modes** — when does this lose money? Don't pretend
  it's bulletproof.
- **Tournament fit** — does it perform better in 1-week leagues, 24-hour
  special events, or both?

Examples aren't expected to win — they're expected to be **honest** and
**runnable**. A clearly-explained losing strategy is more useful than an
opaque winner.

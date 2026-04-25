# MDX AlgoMaster / BotMaster integration

If you already own AlgoMaster or BotMaster, this is the lowest-friction
path into BotPit. There's nothing to install — just paste a webhook URL
into your existing alert config.

## The one URL you need

```
https://www.botpit.io/api/v1/tv/signals?token=aatv_<your-token>&pair=BTC-USDT&size=10&leverage=5
```

Replace:

- `aatv_<your-token>` — get this from <https://www.botpit.io/agents/[id]>
- `pair` — `BTC-USDT`, `ETH-USDT`, `SOL-USDT`, or `PAXG-USDT`
- `size` — % of equity per trade (1–100)
- `leverage` — 1–20

## Setup in AlgoMaster

> [NEEDS-MARK: AlgoMaster screenshots] — placeholder. Fill in once we
> have the actual AlgoMaster alert dialog screenshots.

Rough steps (to be confirmed):

1. Open AlgoMaster's alert configuration.
2. Find the "Webhook URL" field (it's the same field you'd use for any
   third-party webhook integration).
3. Paste the URL above.
4. AlgoMaster's default alert messages (`buy_entry`, `sell_entry`,
   `buy_tp`, `sell_tp`, `buy_sl`, `sell_sl`, `buy_exit`, `sell_exit`)
   are **already in BotPit's event vocabulary** — no message rewriting
   needed.

That's it. The next time AlgoMaster fires an alert, BotPit receives it
and your bot trades.

## Setup in BotMaster

Same as above. BotMaster's automation layer fires the same alert
messages as AlgoMaster, so the URL works identically.

## Why this works out of the box

BotPit's signal vocabulary was designed to match AlgoMaster's alert
labels exactly. The full mapping is documented at
<https://www.botpit.io/llms.txt> under "Event / action vocabulary" — but
you don't need to read it. Every standard AlgoMaster alert resolves
correctly.

## Questions / friction

Open an issue against this repo with the `algomaster` label.

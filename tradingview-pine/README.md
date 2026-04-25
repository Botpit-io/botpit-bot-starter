# TradingView / Pine integration

Already write Pine? You don't need a starter project. The TradingView
alert dialog can POST directly to BotPit's webhook.

## The minimal path

1. Open your strategy in TradingView's Pine Editor.
2. Right-click the chart → "Add alert" → set the **Condition** to your
   strategy.
3. In the **Webhook URL** field, paste:

   ```
   https://www.botpit.io/api/v1/tv/signals?token=aatv_<your-token>&pair=BTC-USDT&size=10&leverage=5
   ```

   (Replace `aatv_<your-token>`, and adjust pair / size / leverage to taste.)

4. In the **Message** field, paste a TradingView template variable that
   resolves to one of BotPit's event labels:

   ```
   {{strategy.order.action}}
   ```

   The TradingView variable `{{strategy.order.action}}` substitutes to
   `"buy"` or `"sell"` (and `"close"` on `strategy.close()` calls). All
   of those are valid BotPit events.

5. Hit **Create**. Now every time your Pine strategy fires an order,
   TradingView POSTs to BotPit and your bot trades.

## Limitations of this path

- TradingView doesn't substitute template variables inside `alert()` calls
  in Pine v5 indicators (only in `strategy()` / `alertcondition()`). If
  you're working from an indicator, you'll need to either (a) hard-code the
  alert message per alert, or (b) move to a `strategy()` script.
- TradingView's free tier rate-limits webhooks. Paid plans are fine for
  per-bar alerts.
- TradingView fires alerts on bar close by default — your stops will fire
  on the next candle, not intra-bar. For tighter stops, build a code bot
  (see [`code-bot/`](../code-bot)) instead.

## Reference Pine snippet

A complete working example showing the right `alert_message` shape:

```pinescript
//@version=5
strategy("BotPit Example", overlay=true)

longSig  = ta.crossover(ta.sma(close, 9), ta.sma(close, 21))
shortSig = ta.crossunder(ta.sma(close, 9), ta.sma(close, 21))

if longSig
    strategy.entry("L", strategy.long,  alert_message="buy_entry")
if shortSig
    strategy.entry("S", strategy.short, alert_message="sell_entry")
if strategy.position_size != 0 and (longSig or shortSig)
    strategy.close_all(alert_message="close")
```

When you create the alert, set the **Message** field to:

```
{{strategy.order.alert_message}}
```

That gives BotPit the literal `"buy_entry"` / `"sell_entry"` / `"close"`
strings the spec expects.

## Full event vocabulary

See <https://www.botpit.io/llms.txt> — search for "Event / action vocabulary".

## Questions / friction

Open an issue against this repo with the `pine` label.

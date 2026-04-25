# Strategy: The Stuber

Fibonacci-pullback bot that takes long/short entries after a confirmed market-structure break, scaled to risk a fixed 3% of equity per trade with a breakeven trail.

## Thesis

The Stuber mechanises a discretionary chart pattern that retail and pro traders alike recognise:

1. **A break in structure** (higher high for longs, lower low for shorts) shifts short-term order flow in that direction.
2. **The first pullback** into the fibonacci 0.618–0.786 retracement of the impulse leg ("the golden pocket") is a high-probability re-entry zone — many traders defend that level with both stops and entries.
3. **Stops below the structure-break origin** define invalidation cleanly: if price returns through the origin, the structure-shift thesis is wrong, and we exit small.

This isn't a novel edge — it's a well-known one. The Stuber's bet is that *systematic, unemotional execution* of the pattern beats discretionary execution of the same pattern, especially under BotPit's drawdown-penalising scoring.

## Pair / timeframe

- **Pair:** BTC-USDT (Binance perpetual mark prices)
- **Timeframe:** 5m candles
- **Cadence:** 10s polling on state + mark price; 60s candle refresh from Binance public klines

## Entry conditions

**Long:**

1. Most recent fractal pivot high (N=5 lookback each side) is *higher* than the prior fractal pivot high → bullish structure break confirmed.
2. Find the lowest low between those two pivot highs → "origin low".
3. Compute fib retracement of (origin low → higher high).
4. If current mark is in 0.618–0.786 retracement zone → enter long.

**Short:** mirror. Pivot low < prior pivot low, find highest high between them, fib retracement up from lower low.

## Risk + sizing

- **Per-trade risk: 3% of current equity.** Sized so that loss-on-stop = 3% via `size_pct × leverage = 300 / stop_dist_pct`.
- **Min-leverage policy:** use the lowest leverage that achieves the required exposure (within `size_pct ≤ 100` and `leverage ≤ 20`). Avoids gratuitous liquidation risk.
- **Stop:** at origin low (long) / origin high (short). The structure-invalidation point.
- **Take profit:** 1.272 fib extension of the impulse leg.
- **Breakeven trail:** once mark moves ≥ 1R in our favor, the local stop is moved to entry. After this, the trade has zero further drawdown contribution.
- If stop distance is below ~0.15% (would require leverage > 20 to achieve 3% risk), trade is **skipped** rather than over-sized.

## Why this should do well in BotPit

- **Tournament scoring is `return − 2 × max_drawdown`.** Drawdown is double-weighted, so anything that limits downside without giving up too much upside is a competitive edge.
- **Tight stops at structure invalidation** keep individual losses ≤ 3% of equity per trade.
- **Breakeven trail** caps drawdown contribution from any trade that moves 1R in our favor — it can no longer turn into a loss.
- **No averaging-down or pyramiding** — the matcher rejects same-side adds anyway.
- **Conservative leverage by default** — typical 5m structure-break stop distances (~1–2%) require 1–3× leverage at 3% risk, well below the 20× cap that ruins most retail bots.
- **Pair selection (BTC):** deepest liquidity, lowest mark-price slippage of the available pairs.

## Known weaknesses

- **Chop kills it.** Sideways markets generate false structure breaks and pullbacks that don't bounce. Expect long stretches of small losses in low-trend regimes.
- **Trend continuation that doesn't pull back** is missed entirely. An aggressive bullish move that runs from the structure break to the 1.272 extension without revisiting the 0.618 zone gives The Stuber zero edge.
- **Fixed fib zone (0.618–0.786) is an oversimplification.** Real discretionary traders weigh confluence (other levels, volume profile, session timing). The Stuber doesn't.
- **No regime filter.** Should arguably skip trades during low-volatility hours or around macro events. Doesn't.
- **Mark-price-based entry timing** means the bot may enter slightly off the candle close — fine for 5m, less ideal for 1m.
- **Fractal pivot detection has natural lookahead delay.** A pivot needs N=5 candles after it to confirm — so structure breaks confirm with a 25-minute lag on 5m. This is honest, not a bug, but it means we're never earliest into a move.
- **Single pair, single direction.** No diversification across BTC/ETH/SOL/PAXG; no hedging.
- **Breakeven trail is a substitute for true scale-out** — see [R4-1](https://github.com/Botpit-io/botpit-bot-starter/issues/12). Real scale-out (close 50% at 1R, runner stays with stop at BE) would lock in *realized* profit at the partial-close price, which the breakeven trail doesn't. When R4-1 ships, this is a trivial upgrade.

## Future improvements (parked, not in v1)

- **Real scale-out** when [R4-1](https://github.com/Botpit-io/botpit-bot-starter/issues/12) ships — close 50% at ~1R, leave runner with BE stop for the 1.272 extension.
- **Multi-pair execution** across BTC/ETH/SOL with correlation-aware sizing.
- **Volatility regime filter** to suppress trades in chop.
- **Asymmetric risk** — vary risk per trade based on setup quality (deeper structure break = larger size).

## Risk parameters (summary)

| Parameter | Value |
|---|---|
| Pair | BTC-USDT |
| Timeframe | 5m |
| Risk per trade | 3% of equity |
| Stop placement | Origin low (long) / origin high (short) |
| Take profit | 1.272 fib extension |
| Breakeven trail trigger | Mark moves ≥ 1R in favor |
| Pivot lookback (N) | 5 candles each side |
| Fib entry zone | 0.618 to 0.786 retracement |
| Max leverage | 20× (platform cap; typically 1–3× used) |
| Min trade-size policy | Skip if stop too tight to size within 20× leverage |

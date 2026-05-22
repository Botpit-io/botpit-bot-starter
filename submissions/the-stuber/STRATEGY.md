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
- **Timeframe:** 15m candles (raised from 5m for chop tolerance; `BOTPIT_TIMEFRAME`)
- **Higher timeframe:** 4h, used by the trend-of-trend filter (R6-3)
- **Cadence:** 10s polling on state + mark price; 60s candle refresh (4h candles every 5 min)
- **Market data:** Binance USDⓈ-M futures primary → FMP crypto feed (if `STUBER_FMP_KEY` set) → Bybit linear perps — three independent IP-reputation surfaces, so a single-venue ban (e.g. Binance `418` on a shared PaaS egress IP) doesn't take the bot offline (R6-16)

## Entry conditions

**Long:**

1. Most recent fractal pivot high (N=10 lookback each side; `STUBER_PIVOT_N`) is *higher* than the prior fractal pivot high → bullish structure break confirmed.
2. Find the lowest low between those two pivot highs → "origin low".
3. Compute fib retracement of (origin low → higher high).
4. If current mark is in 0.618–0.786 retracement zone → enter long.

**Short:** mirror. Pivot low < prior pivot low, find highest high between them, fib retracement up from lower low.

**Filters applied before any entry:**

- **Trend-of-trend (R6-3):** compute the most recent confirmed structure event on the 4h chart. Skip 15m longs while the 4h structure is bearish, and 15m shorts while it's bullish. A "neutral" 4h (no confirmed break) allows either side.
- **News-flat:** if `/api/v1/tv/state`'s `macro_calendar.next` shows a high-impact US release (CPI/NFP/FOMC/…) within `STUBER_MACRO_BUFFER_MIN` minutes (default 30), decline new entries — and close any *existing* position — until the print is past. Standard prop-firm "no trading around scheduled news" rule; set the buffer to `0` to disable.

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
- **Conservative leverage by default** — typical 15m structure-break stop distances (~1–2%) require 1–3× leverage at 3% risk, well below the 20× cap that ruins most retail bots.
- **Pair selection (BTC):** deepest liquidity, lowest mark-price slippage of the available pairs.

## Known weaknesses

- **Chop kills it.** Sideways markets generate false structure breaks and pullbacks that don't bounce. Expect long stretches of small losses in low-trend regimes.
- **Trend continuation that doesn't pull back** is missed entirely. An aggressive bullish move that runs from the structure break to the 1.272 extension without revisiting the 0.618 zone gives The Stuber zero edge.
- **Fixed fib zone (0.618–0.786) is an oversimplification.** Real discretionary traders weigh confluence (other levels, volume profile, session timing). The Stuber doesn't.
- **Partial regime awareness only.** A 4h trend-of-trend filter (R6-3) suppresses entries that disagree with the higher-timeframe structure, and the bot now goes news-flat ahead of scheduled high-impact macro prints (CPI/NFP/FOMC) via `/api/v1/tv/state`'s `macro_calendar`. Still no low-volatility-hours filter, and no notion of *unscheduled* shocks.
- **Mark-price-based entry timing** means the bot may enter slightly off the candle close — fine for 15m, less ideal for sub-5m.
- **Fractal pivot detection has natural lookahead delay.** A pivot needs N=10 candles after it to confirm — so on 15m, structure breaks confirm ~2.5h after the pivot. The 4h trend filter adds further lag of its own. This is honest, not a bug, but it means we're never earliest into a move; the bet is on the *quality* of confirmed setups, not speed.
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
| Timeframe | 15m (was 5m) |
| Risk per trade | 3% of equity |
| Stop placement | Origin low (long) / origin high (short) |
| Take profit | 1.272 fib extension |
| Breakeven trail trigger | Mark moves ≥ 1R in favor |
| Pivot lookback (N) | 10 candles each side (was 5) |
| Fib entry zone | 0.618 to 0.786 retracement |
| Higher-TF trend filter | 4h trend-of-trend; skip entries against it (R6-3) |
| Macro blackout | News-flat within 30 min of a high-impact print (`STUBER_MACRO_BUFFER_MIN`, 0=off) |
| Max leverage | 20× (platform cap; typically 1–3× used) |
| Min trade-size policy | Skip if stop too tight to size within 20× leverage |

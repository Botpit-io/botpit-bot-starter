# State management for BotPit bots

If your bot tracks position state locally — stop levels, take-profit prices, breakeven flags, "have I closed this trade yet" — read this. It's a pattern that catches every bot author once.

## The problem

Bots that hold a position need to know things the BotPit API doesn't surface to them on every tick: where the stop is, where the TP is, whether the breakeven trail has been moved, whether the trade is "ours" vs. inherited from a prior process. The natural shape of this is a local in-memory cache — call it `StopMemory` or `PositionState` or whatever fits your language.

That cache has two failure modes that can both leave a position open with no client-side risk management:

1. **Cleared too eagerly.** Your bot sends a CLOSE, gets `status: queued` back, and clears its local state on the assumption that the close will happen. The matching engine then rejects the close (transient feed issue, position-state mismatch, race with another fill) — but your bot already moved on. The position stays open. Your bot's watcher sees `memory.stop_price is None`, returns `None`, never re-emits.
2. **Never re-hydrated.** Your bot restarts (Railway redeploy, OOM, process crash). On the next tick, the matching engine still reports an open position, but your in-memory state is fresh — no stop, no TP, no entry price. Your bot heartbeats indefinitely with no risk management on a real position.

Both end in the same place: an orphaned position with no automatic exit.

## The rule: observe, don't infer

The fix is one principle, applied in two places:

> **Never derive position state from an API response shape. Always read it from the next snapshot of `snap.open_position`.**

Concretely:

- **Don't clear local state when you *send* a CLOSE.** Clear it when you *observe* `snap.open_position is None`.
- **Don't trust that local state is hydrated when a position exists.** On every tick, if the snapshot shows a position but your memory has no entry price, install a fallback stop *now*.

The two halves are symmetric. One handles "API response said the close happened but it didn't"; the other handles "process restarted and lost track."

## Drop-in code

This is the pattern in Python; translate to your language. The full version lives in `submissions/the-stuber/bot.py` if you want to read it inline.

### 1. Add a "close was emitted at" timestamp to your local state

```python
@dataclass
class StopMemory:
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    entry_price: Optional[float] = None
    # ... your other fields ...
    last_close_emit_at: Optional[float] = None  # epoch seconds; throttles re-emit
```

This lets you throttle re-emission so you don't spam CLOSE every tick if the engine isn't accepting them.

### 2. Throttle CLOSE re-emission

If a recent CLOSE didn't fill, the watcher will keep wanting to fire on every tick. Stop it from doing so more than once per minute:

```python
CLOSE_RETRY_THROTTLE_S = 60.0

def watch_stops(snap, mark_price):
    if snap.open_position is None:
        return None
    if memory.last_close_emit_at is not None:
        if time.time() - memory.last_close_emit_at < CLOSE_RETRY_THROTTLE_S:
            return None
    # ... rest of stop/TP check logic ...
```

### 3. When sending CLOSE, only update the timestamp — don't clear state

```python
def apply_decision(api, decision, snap, pair):
    if decision.action == Action.CLOSE:
        if snap.open_position is None:
            return
        resp = api.send_signal(side="close", pair=pair, size_pct=100, leverage=1)
        log.info("CLOSE sent -> %s", resp.get("status"))
        # Mark the emit time so the throttle works,
        # but don't clear stop/tp/entry — those get cleared in the run loop
        # only when we observe the position is actually flat.
        memory.last_close_emit_at = time.time()
```

### 4. Confirmed-flat clear and orphan recovery on every tick

In your main loop, right after building the snapshot:

```python
ORPHAN_FALLBACK_STOP_PCT = 1.5
ORPHAN_FALLBACK_TP_PCT = 3.0

while True:
    snap = build_snapshot(api, PAIR, rules)
    mark = get_mark_price(PAIR)

    # Confirmed-flat clear: position is verifiably gone, safe to wipe memory.
    if snap.open_position is None and memory.entry_price is not None:
        log.info("position confirmed closed — clearing local stop memory")
        memory.stop_price = None
        memory.take_profit_price = None
        memory.entry_price = None
        memory.last_close_emit_at = None
        # ... clear your other fields ...

    # Orphan recovery: position exists but bot has no stop tracking.
    # Install a conservative fallback stop so the position is never silently un-watched.
    if snap.open_position is not None and memory.entry_price is None:
        entry = float(snap.open_position["entry_price"])
        side = snap.open_position["side"]
        if side == "long":
            memory.stop_price = entry * (1 - ORPHAN_FALLBACK_STOP_PCT / 100)
            memory.take_profit_price = entry * (1 + ORPHAN_FALLBACK_TP_PCT / 100)
        else:
            memory.stop_price = entry * (1 + ORPHAN_FALLBACK_STOP_PCT / 100)
            memory.take_profit_price = entry * (1 - ORPHAN_FALLBACK_TP_PCT / 100)
        memory.entry_price = entry
        log.warning("orphan position detected — installed fallback stop @ %.2f, tp @ %.2f",
                    memory.stop_price, memory.take_profit_price)

    # ... rest of your loop: watcher, decide(), apply ...
```

## Picking your fallback stop levels

The orphan-recovery fallback is intentionally conservative — it's protecting an already-orphaned position, not implementing your strategy. Pick numbers that get you out without thinking too hard about price action:

- **1.5% from entry** is a reasonable default for major pairs (BTC, ETH). It's tight enough that an orphan installed during normal volatility will exit promptly; loose enough that a normal mid-trade restart won't immediately stop you out.
- For higher-volatility pairs (memecoins, low-liquidity perps), bump to 3%.
- For lower-volatility (gold, indices), drop to 0.75%.

Re-tune per your own strategy's risk profile. Don't try to recover the original stop level from API data — you usually can't, and a wrong fallback is worse than a generic conservative one.

## What this pattern doesn't fix

- **Strategy bugs that emit CLOSE against positions that don't exist.** That's the inverse failure class — your `decide()` logic thinks it has a position when the engine sees flat. Fix: read `snap.open_position` *before* deciding to close, and reset your internal state when it disagrees with the engine.
- **Engine-side queue or feed problems.** If BotPit's matching engine is rejecting your closes for `PRICE_FEED_STALE` or queueing them indefinitely, this pattern keeps your bot's local state honest, but it doesn't make the engine fill the trade. Surface that to BotPit as an issue.

## Related issues

- [#27 (R6-9)](https://github.com/Botpit-io/botpit-bot-starter/issues/27) — the discovery: optimistic state-clear + price feed outage = orphaned position
- [#12 (R4-1)](https://github.com/Botpit-io/botpit-bot-starter/issues/12) — partial-close support (separate from this pattern, but related risk-management surface)

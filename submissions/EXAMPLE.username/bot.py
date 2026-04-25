"""
BotPit minimal-but-safe Python bot.

Spec: https://www.botpit.io/llms.txt

ARCHITECTURE
============

Everything is a poll loop. Every TICK_SECONDS we:
  1. Read /api/v1/tv/state                  — what's actually true
  2. Run watch_stops()                      — fire client-side stops if hit
  3. Run decide()                           — your strategy decides next action
  4. Apply the decision (send_signal)       — POST /api/v1/tv/signals
  5. Log a heartbeat                        — so you can verify uptime

Why this shape: BotPit doesn't enforce server-side stops or take-profits.
If your bot crashes between an entry and its stop, the position keeps
running unprotected. So the watcher must run on every tick, even when
no entry conditions are met.

WHERE YOUR STRATEGY GOES
========================

Find the `decide()` function below. Everything else is plumbing — leave
it alone unless you're changing the bot's *shape* (e.g. switching to
multiple pairs in parallel).

The starter ships with a placeholder `decide()` that does nothing. Your
job is to return one of:
  - Decision(Action.OPEN_LONG,  size_pct=10, leverage=5, stop_pct=1.5)
  - Decision(Action.OPEN_SHORT, size_pct=10, leverage=5, stop_pct=1.5)
  - Decision(Action.CLOSE)
  - Decision(Action.HOLD)
"""

from __future__ import annotations

import os
import sys
import time
import enum
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

# ---------- Config ----------

API_BASE = os.getenv("BOTPIT_API_BASE", "https://www.botpit.io")
TOKEN = os.environ.get("BOTPIT_TV_TOKEN")
PAIR = os.getenv("BOTPIT_PAIR", "BTC-USDT")
TICK_SECONDS = int(os.getenv("BOTPIT_TICK_SECONDS", "10"))

if not TOKEN:
    sys.exit("BOTPIT_TV_TOKEN not set. Copy .env.example to .env and paste your aatv_ token.")

logging.basicConfig(
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger("bot")


# ---------- Strategy interface ----------

class Action(enum.Enum):
    HOLD = "hold"
    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE = "close"


@dataclass
class Decision:
    action: Action
    size_pct: float = 10.0       # % of equity per trade (only for OPEN_*)
    leverage: int = 5            # 1..20 (only for OPEN_*)
    stop_pct: float = 1.5        # client-side stop distance % (only for OPEN_*)
    take_profit_pct: float = 3.0 # client-side TP distance %  (only for OPEN_*)


# ---------- API helpers ----------

class BotPit:
    def __init__(self, base: str, token: str):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"

    def tournament(self) -> dict:
        r = self.session.get(f"{self.base}/api/v1/tv/tournament", timeout=8)
        r.raise_for_status()
        return r.json()

    def state(self) -> dict:
        r = self.session.get(f"{self.base}/api/v1/tv/state", timeout=8)
        r.raise_for_status()
        return r.json()

    def send_signal(self, event: str, *, size_pct: float, leverage: int, pair: str) -> dict:
        # event in: buy_entry / sell_entry / close / buy_exit / sell_exit / ...
        body = {
            "event": event,
            "pair": pair,
            "size_pct_equity": size_pct,
            "leverage": leverage,
            "nonce": int(time.time() * 1000),
        }
        r = self.session.post(f"{self.base}/api/v1/tv/signals", json=body, timeout=8)
        # 202 is success ("queued"). 400/401 are real errors.
        if r.status_code >= 400:
            log.warning("signal rejected: %s %s", r.status_code, r.text[:200])
            return {"status": "rejected", "http": r.status_code, "raw": r.text}
        return r.json()


# ---------- Mark price (for client-side stops) ----------
#
# We use Binance's public futures mark-price endpoint — no auth needed and
# it's the same source BotPit's matching engine uses for fills, so your
# stop levels will line up with what BotPit sees.

BINANCE_MARK = "https://fapi.binance.com/fapi/v1/premiumIndex"

def get_mark_price(pair: str) -> float:
    # pair like "BTC-USDT" → Binance symbol "BTCUSDT"
    symbol = pair.replace("-", "")
    r = requests.get(BINANCE_MARK, params={"symbol": symbol}, timeout=5)
    r.raise_for_status()
    return float(r.json()["markPrice"])


# ---------- Local state cache ----------
#
# We rebuild this from /api/v1/tv/state on every tick — never trust the
# in-memory copy after a network blip. This dataclass exists only so the
# strategy fn has a clean shape to read.

@dataclass
class Snapshot:
    equity_usd: float
    return_pct: float
    drawdown_pct: float
    open_position: Optional[Dict[str, Any]]  # the row from positions[], or None
    last_fill_price: Optional[float]         # last entry fill price (for stop math)
    pair_config: Dict[str, Any]              # tournament rules

    # Filled in by watch_stops if the user set them via decide()
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None


@dataclass
class StopMemory:
    """Stops aren't persisted server-side. We remember them in-process and
    re-derive on restart from the last entry fill + the user's last decision.
    Restart safety: if the bot crashes mid-trade and restarts, it'll see the
    open position via /state but won't know the stop level — it'll re-enter
    "no stop" mode until the next entry. That's safer than guessing."""
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None


memory = StopMemory()


# ---------- Strategy — REPLACE ME ----------
#
# This is the only function your LLM needs to fill in. Read snap to understand
# the world, return what to do next. The plumbing handles everything else.

def decide(snap: Snapshot, mark_price: float) -> Decision:
    """
    PLACEHOLDER STRATEGY — replace with your own.

    The shipped behaviour: do nothing. The bot enters the arena but never
    trades. Replace this function with your strategy.

    Examples to ask your LLM for:

      - "Open long when mark price drops 1% from the 60-tick rolling high.
         Close when up 0.5% or down 1%."
      - "Buy when RSI(14) crosses below 30, close when it crosses above 70."
      - "On the 1-hour boundary, flip to whichever side BTC funding rate is
         paying."

    Return one of:
      Decision(Action.HOLD)
      Decision(Action.OPEN_LONG,  size_pct=10, leverage=5, stop_pct=1.5)
      Decision(Action.OPEN_SHORT, size_pct=10, leverage=5, stop_pct=1.5)
      Decision(Action.CLOSE)
    """
    return Decision(Action.HOLD)


# ---------- Stop watcher ----------

def watch_stops(snap: Snapshot, mark_price: float) -> Optional[Decision]:
    """If the open position has a stop or TP set and the mark price has
    crossed it, return a CLOSE decision. Returns None otherwise."""
    if snap.open_position is None:
        return None
    side = snap.open_position["side"]
    if memory.stop_price is not None:
        if side == "long" and mark_price <= memory.stop_price:
            log.info("STOP HIT (long) — mark %.2f ≤ stop %.2f", mark_price, memory.stop_price)
            return Decision(Action.CLOSE)
        if side == "short" and mark_price >= memory.stop_price:
            log.info("STOP HIT (short) — mark %.2f ≥ stop %.2f", mark_price, memory.stop_price)
            return Decision(Action.CLOSE)
    if memory.take_profit_price is not None:
        if side == "long" and mark_price >= memory.take_profit_price:
            log.info("TP HIT (long) — mark %.2f ≥ tp %.2f", mark_price, memory.take_profit_price)
            return Decision(Action.CLOSE)
        if side == "short" and mark_price <= memory.take_profit_price:
            log.info("TP HIT (short) — mark %.2f ≤ tp %.2f", mark_price, memory.take_profit_price)
            return Decision(Action.CLOSE)
    return None


# ---------- Main loop ----------

def build_snapshot(api: BotPit, pair: str, rules: dict) -> Snapshot:
    s = api.state()
    open_pos = next((p for p in s["positions"] if p["pair"] == pair), None)
    last_fill_price = None
    if open_pos:
        # Last entry fill on this pair (skip the close fills if any)
        for f in s["recent_fills"]:
            if f["pair"] == pair and f["side"] == open_pos["side"]:
                last_fill_price = f["price"]
                break
    return Snapshot(
        equity_usd=s["equity"]["current_usd"],
        return_pct=s["equity"]["return_pct"],
        drawdown_pct=s["equity"]["drawdown_pct"],
        open_position=open_pos,
        last_fill_price=last_fill_price,
        pair_config=rules,
    )


def apply_decision(api: BotPit, decision: Decision, snap: Snapshot, pair: str) -> None:
    if decision.action == Action.HOLD:
        return

    if decision.action in (Action.OPEN_LONG, Action.OPEN_SHORT):
        if snap.open_position is not None:
            # The matcher would reject POSITION_ADD_UNSUPPORTED — skip the call.
            log.info("decide() wants %s but already %s; close first.",
                     decision.action.value, snap.open_position["side"])
            return
        event = "buy_entry" if decision.action == Action.OPEN_LONG else "sell_entry"
        resp = api.send_signal(
            event=event, size_pct=decision.size_pct,
            leverage=decision.leverage, pair=pair,
        )
        log.info("OPEN %s sent → %s", decision.action.value, resp.get("status"))
        # Set the client-side stop/TP off the *expected* fill price — we'll
        # refresh from snap.last_fill_price next tick once the fill lands.
        # That's good enough for the watcher's first check.
        try:
            mark = get_mark_price(pair)
            if decision.action == Action.OPEN_LONG:
                memory.stop_price = mark * (1 - decision.stop_pct / 100)
                memory.take_profit_price = mark * (1 + decision.take_profit_pct / 100)
            else:
                memory.stop_price = mark * (1 + decision.stop_pct / 100)
                memory.take_profit_price = mark * (1 - decision.take_profit_pct / 100)
            log.info("stop set @ %.2f, tp @ %.2f", memory.stop_price, memory.take_profit_price)
        except Exception as e:
            log.warning("couldn't set client-side stop: %s", e)
        return

    if decision.action == Action.CLOSE:
        if snap.open_position is None:
            return  # already flat — no-op (matcher would return NO_POSITION_TO_CLOSE)
        resp = api.send_signal(
            event="close", size_pct=100, leverage=1, pair=pair,
        )
        log.info("CLOSE sent → %s", resp.get("status"))
        memory.stop_price = None
        memory.take_profit_price = None


def run() -> None:
    api = BotPit(API_BASE, TOKEN)

    log.info("starting up against %s", API_BASE)
    t = api.tournament()
    rules = t["rules"]
    tournament = t["tournament"]
    log.info("tournament: %s (ends %s)", tournament["name"], tournament["ends_at"])
    log.info("rules: leverage_cap=%dx allowed_pairs=%s starting_equity=$%s",
             rules["leverage_cap"], rules["allowed_pairs"], rules["starting_equity_usd"])
    if PAIR not in rules["allowed_pairs"]:
        sys.exit(f"PAIR={PAIR} not in allowed_pairs {rules['allowed_pairs']}; set BOTPIT_PAIR.")

    last_heartbeat = 0.0
    HEARTBEAT_EVERY = 60  # seconds

    while True:
        try:
            snap = build_snapshot(api, PAIR, rules)
            mark = get_mark_price(PAIR)

            # 1. Check stops first — never miss a stop because strategy is busy
            stop_decision = watch_stops(snap, mark)
            if stop_decision:
                apply_decision(api, stop_decision, snap, PAIR)
                snap = build_snapshot(api, PAIR, rules)  # re-read after close

            # 2. Run strategy
            decision = decide(snap, mark)
            apply_decision(api, decision, snap, PAIR)

            # 3. Heartbeat (rate-limited so the log doesn't drown)
            now = time.time()
            if now - last_heartbeat > HEARTBEAT_EVERY:
                pos_str = (
                    f"{snap.open_position['side']} {snap.open_position['size_units']:.4f} {PAIR} @ ${snap.open_position['entry_price']:.2f}"
                    if snap.open_position else "flat"
                )
                log.info("hb: equity=$%.2f return=%+.2f%% dd=%.2f%% pos=[%s] mark=%.2f",
                         snap.equity_usd, snap.return_pct, snap.drawdown_pct, pos_str, mark)
                last_heartbeat = now

        except requests.RequestException as e:
            log.warning("network blip: %s — backing off 5s", e)
            time.sleep(5)
            continue
        except Exception as e:
            log.exception("unexpected error: %s", e)
            time.sleep(5)
            continue

        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    run()

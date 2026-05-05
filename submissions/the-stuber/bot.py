"""
The Stuber — Fibonacci pullback after structure break.

Strategy: long/short entries on pullback into the 0.618-0.786 fib zone after
a confirmed market-structure break. Stop at origin low/high, TP at 1.272
extension. Risk-based sizing for 3% loss on stop. Breakeven trail at 1R.

Built on the BotPit code-bot starter (HMAC path).
See STRATEGY.md for the full thesis + weaknesses.
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

# ---------- Config ----------

API_BASE = os.getenv("BOTPIT_API_BASE", "https://www.botpit.io")
PUBKEY = os.environ.get("BOTPIT_AGENT_PUBKEY")
SECRET = os.environ.get("BOTPIT_AGENT_SECRET")
PAIR = os.getenv("BOTPIT_PAIR", "BTC-USDT")
TIMEFRAME = os.getenv("BOTPIT_TIMEFRAME", "5m")
TICK_SECONDS = int(os.getenv("BOTPIT_TICK_SECONDS", "10"))

# Strategy params (tweak via env if needed)
PIVOT_LOOKBACK = int(os.getenv("STUBER_PIVOT_N", "5"))
FIB_ZONE_LOW = float(os.getenv("STUBER_FIB_LOW", "0.618"))
FIB_ZONE_HIGH = float(os.getenv("STUBER_FIB_HIGH", "0.786"))
FIB_TP_EXTENSION = float(os.getenv("STUBER_TP_EXT", "1.272"))
RISK_PCT_EQUITY = float(os.getenv("STUBER_RISK_PCT", "3.0"))
MAX_LEVERAGE = int(os.getenv("STUBER_MAX_LEVERAGE", "20"))
CANDLES_TO_FETCH = int(os.getenv("STUBER_CANDLES", "100"))
CANDLE_REFRESH_SECONDS = int(os.getenv("STUBER_CANDLE_REFRESH", "60"))

# Higher-timeframe trend filter (R6-3 — trend-of-trend)
# Skip 15m shorts when the most recent 4h structure was a bullish break (HH > prior HH),
# and 15m longs when the most recent 4h structure was a bearish break (LL < prior LL).
HTF_TIMEFRAME = os.getenv("STUBER_HTF_TIMEFRAME", "4h")
HTF_PIVOT_N = int(os.getenv("STUBER_HTF_PIVOT_N", "5"))
HTF_CANDLE_REFRESH_SECONDS = int(os.getenv("STUBER_HTF_CANDLE_REFRESH", "300"))  # 5 min

logging.basicConfig(format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S", level=logging.INFO)
log = logging.getLogger("the-stuber")


# ---------- Strategy interface (matches starter contract) ----------

class Action(enum.Enum):
    HOLD = "hold"
    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE = "close"


@dataclass
class Decision:
    action: Action
    size_pct: float = 10.0
    leverage: int = 5
    stop_pct: float = 1.5
    take_profit_pct: float = 3.0


@dataclass
class Snapshot:
    equity_usd: float
    return_pct: float
    drawdown_pct: float
    open_position: Optional[Dict[str, Any]]
    last_fill_price: Optional[float]
    pair_config: Dict[str, Any]


@dataclass
class StopMemory:
    """Client-side stop/TP state. The breakeven-trail logic mutates `stop_price`
    in place; the watcher loop reads it on every tick and fires CLOSE if hit.

    Isolated here so swapping in a real scale-out implementation (when
    https://github.com/Botpit-io/botpit-bot-starter/issues/12 / R4-1 ships)
    is a small, contained change rather than a rewrite."""
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    entry_price: Optional[float] = None
    original_stop_pct: Optional[float] = None
    moved_to_breakeven: bool = False
    last_close_reason: Optional[str] = None  # set by watcher, read by apply_decision for log_decision


memory = StopMemory()


# ---------- Candle cache (Binance public klines) ----------

BINANCE_KLINES = "https://fapi.binance.com/fapi/v1/klines"


@dataclass
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float


_candle_cache: List[Candle] = []
_candle_cache_at: float = 0.0


def _fetch_candles(pair: str, timeframe: str, limit: int) -> List[Candle]:
    symbol = pair.replace("-", "")
    r = requests.get(
        BINANCE_KLINES,
        params={"symbol": symbol, "interval": timeframe, "limit": limit},
        timeout=5,
    )
    r.raise_for_status()
    return [
        Candle(
            open_time=int(k[0]),
            open=float(k[1]),
            high=float(k[2]),
            low=float(k[3]),
            close=float(k[4]),
        )
        for k in r.json()
    ]


def _get_candles(pair: str, timeframe: str = TIMEFRAME) -> List[Candle]:
    """Refresh cache if stale; otherwise return cached candles. Returns
    whatever's cached on fetch failure (possibly empty list)."""
    global _candle_cache, _candle_cache_at
    now = time.time()
    if not _candle_cache or (now - _candle_cache_at) > CANDLE_REFRESH_SECONDS:
        try:
            _candle_cache = _fetch_candles(pair, timeframe, CANDLES_TO_FETCH)
            _candle_cache_at = now
        except Exception as e:
            log.warning("candle fetch failed: %s — using cache (%d candles)", e, len(_candle_cache))
    return _candle_cache


# Higher-timeframe candle cache for the trend-of-trend filter (R6-3).
_htf_candle_cache: List[Candle] = []
_htf_candle_cache_at: float = 0.0


def _get_htf_candles(pair: str = PAIR) -> List[Candle]:
    """Same shape as _get_candles but for the higher timeframe used by the
    trend-of-trend filter. Refreshes every HTF_CANDLE_REFRESH_SECONDS (default
    5 min) since 4h candles change rarely."""
    global _htf_candle_cache, _htf_candle_cache_at
    now = time.time()
    if not _htf_candle_cache or (now - _htf_candle_cache_at) > HTF_CANDLE_REFRESH_SECONDS:
        try:
            _htf_candle_cache = _fetch_candles(pair, HTF_TIMEFRAME, CANDLES_TO_FETCH)
            _htf_candle_cache_at = now
        except Exception as e:
            log.warning("HTF candle fetch failed: %s — using cache (%d candles)", e, len(_htf_candle_cache))
    return _htf_candle_cache


def _detect_htf_trend(candles: List[Candle], n: int) -> str:
    """Returns 'bullish' | 'bearish' | 'neutral' based on the most recent
    confirmed structure event on the higher timeframe.

    'bullish' = most recent confirmed pivot high broke the prior pivot high
                AND that event is more recent than any LL break.
    'bearish' = mirror with pivot lows.
    'neutral' = neither break is confirmed (or not enough candles)."""
    pivot_highs, pivot_lows = _find_pivots(candles, n)

    bullish_break_idx = None
    if len(pivot_highs) >= 2 and candles[pivot_highs[-1]].high > candles[pivot_highs[-2]].high:
        bullish_break_idx = pivot_highs[-1]

    bearish_break_idx = None
    if len(pivot_lows) >= 2 and candles[pivot_lows[-1]].low < candles[pivot_lows[-2]].low:
        bearish_break_idx = pivot_lows[-1]

    if bullish_break_idx is None and bearish_break_idx is None:
        return "neutral"
    if bullish_break_idx is None:
        return "bearish"
    if bearish_break_idx is None:
        return "bullish"
    # Both confirmed — whichever pivot is more recent wins
    return "bullish" if bullish_break_idx > bearish_break_idx else "bearish"


# ---------- Fractal pivot detection ----------

def _find_pivots(candles: List[Candle], n: int) -> Tuple[List[int], List[int]]:
    """Fractal pivots: a pivot high at i if candles[i].high == max of the
    [i-n .. i+n] window; pivot low symmetrically. Returns indices."""
    highs: List[int] = []
    lows: List[int] = []
    if len(candles) < 2 * n + 1:
        return highs, lows
    for i in range(n, len(candles) - n):
        window = candles[i - n : i + n + 1]
        if candles[i].high == max(c.high for c in window):
            highs.append(i)
        if candles[i].low == min(c.low for c in window):
            lows.append(i)
    return highs, lows


# ---------- Setup detection ----------

@dataclass
class LongSetup:
    origin_low: float
    higher_high: float
    fib_low: float       # 0.786 retracement = bottom of entry zone (lower price)
    fib_high: float      # 0.618 retracement = top of entry zone (higher price)
    take_profit: float   # 1.272 fib extension above the higher high
    stop: float          # at origin low


@dataclass
class ShortSetup:
    origin_high: float
    lower_low: float
    fib_low: float       # 0.618 retracement = bottom of entry zone (lower price)
    fib_high: float      # 0.786 retracement = top of entry zone (higher price)
    take_profit: float   # 1.272 fib extension below the lower low
    stop: float          # at origin high


def _detect_long_setup(candles: List[Candle], n: int) -> Optional[LongSetup]:
    pivot_highs, _ = _find_pivots(candles, n)
    if len(pivot_highs) < 2:
        return None

    last_idx = pivot_highs[-1]
    prev_idx = pivot_highs[-2]
    last_ph = candles[last_idx].high
    prev_ph = candles[prev_idx].high

    # Bullish structure break: most recent pivot high > prior pivot high
    if last_ph <= prev_ph:
        return None

    # Origin low: lowest low between the two pivot highs (the impulse-leg low)
    between = candles[prev_idx : last_idx + 1]
    origin_low = min(c.low for c in between)
    if last_ph <= origin_low:
        return None

    leg = last_ph - origin_low
    fib_high = last_ph - FIB_ZONE_LOW * leg     # 0.618 retracement
    fib_low = last_ph - FIB_ZONE_HIGH * leg     # 0.786 retracement
    take_profit = last_ph + (FIB_TP_EXTENSION - 1.0) * leg

    return LongSetup(
        origin_low=origin_low,
        higher_high=last_ph,
        fib_low=fib_low,
        fib_high=fib_high,
        take_profit=take_profit,
        stop=origin_low,
    )


def _detect_short_setup(candles: List[Candle], n: int) -> Optional[ShortSetup]:
    _, pivot_lows = _find_pivots(candles, n)
    if len(pivot_lows) < 2:
        return None

    last_idx = pivot_lows[-1]
    prev_idx = pivot_lows[-2]
    last_pl = candles[last_idx].low
    prev_pl = candles[prev_idx].low

    if last_pl >= prev_pl:
        return None

    between = candles[prev_idx : last_idx + 1]
    origin_high = max(c.high for c in between)
    if last_pl >= origin_high:
        return None

    leg = origin_high - last_pl
    fib_low = last_pl + FIB_ZONE_LOW * leg      # 0.618 retracement (above LL)
    fib_high = last_pl + FIB_ZONE_HIGH * leg    # 0.786 retracement
    take_profit = last_pl - (FIB_TP_EXTENSION - 1.0) * leg

    return ShortSetup(
        origin_high=origin_high,
        lower_low=last_pl,
        fib_low=fib_low,
        fib_high=fib_high,
        take_profit=take_profit,
        stop=origin_high,
    )


# ---------- Risk-based sizing ----------

def _size_for_risk(
    stop_dist_pct: float,
    target_risk_pct: float = RISK_PCT_EQUITY,
    max_leverage: int = MAX_LEVERAGE,
) -> Optional[Tuple[float, int]]:
    """
    Loss-on-stop = stop_dist_pct × (size_pct/100) × leverage
    For target_risk_pct: required `size_pct × leverage = (target_risk_pct × 100) / stop_dist_pct`.

    Returns (size_pct, leverage), preferring the lowest leverage that fits.
    Returns None if stop is too tight to fit within max_leverage.
    """
    if stop_dist_pct <= 0:
        return None
    required_product = (target_risk_pct * 100.0) / stop_dist_pct
    if required_product <= 100.0:
        return required_product, 1
    if required_product <= 100.0 * max_leverage:
        leverage = int(math.ceil(required_product / 100.0))
        size_pct = required_product / leverage
        return size_pct, leverage
    return None


# ---------- The Stuber strategy ----------

def decide(snap: Snapshot, mark_price: float) -> Decision:
    """
    The Stuber: long/short on pullback into the 0.618-0.786 fib zone after
    a confirmed structure break. Wraps the inner logic in a try/except that
    defaults to HOLD — preferring to do nothing over crashing.
    """
    try:
        return _decide_inner(snap, mark_price)
    except Exception as e:
        log.warning("decide() error: %s — defaulting to HOLD", e)
        return Decision(Action.HOLD)


# Tracks the last logged HOLD key; we only log when the structural reason
# changes (different setup, different zone), not when mark price drifts.
_last_hold_key: Optional[str] = None


def _hold(key: str, message: str, payload: Optional[Dict[str, Any]] = None) -> Decision:
    """Return a HOLD decision and log message iff `key` changed since last tick.
    The key is the *structural* deduplication signal (e.g. setup identity);
    the message is the human-readable line which may include live mark price.
    On reason change, also fires a fire-and-forget /api/v1/decisions record so
    dashboards can render WHY the bot chose to hold (no strategy duplication)."""
    global _last_hold_key
    if key != _last_hold_key:
        log.info("HOLD: %s", message)
        _last_hold_key = key
        if _api is not None:
            _api.log_decision(action="hold", reason=message[:280], payload=payload)
    return Decision(Action.HOLD)


def _decide_inner(snap: Snapshot, mark_price: float) -> Decision:
    # If position is open: maybe move stop to breakeven, then HOLD.
    # All exits are handled by the watcher (stop / TP / BE) — decide() never
    # issues CLOSE itself except via that path.
    if snap.open_position is not None:
        side = snap.open_position.get("side", "?")
        return _hold(f"managing:{side}", f"managing open {side} position")

    candles = _get_candles(PAIR)
    if len(candles) < 2 * PIVOT_LOOKBACK + 2:
        return _hold(
            f"warming:{len(candles)}",
            f"warming up: {len(candles)} candles cached (need {2 * PIVOT_LOOKBACK + 2})",
        )

    # R6-3: trend-of-trend filter — skip entries that disagree with the higher-timeframe
    # structure. Computed once per tick; "neutral" means no confirmed HTF break, allow either side.
    htf_candles = _get_htf_candles(PAIR)
    htf_trend = (
        _detect_htf_trend(htf_candles, HTF_PIVOT_N)
        if len(htf_candles) >= 2 * HTF_PIVOT_N + 2
        else "neutral"
    )

    long_setup = _detect_long_setup(candles, PIVOT_LOOKBACK)
    if long_setup and long_setup.fib_low <= mark_price <= long_setup.fib_high:
        if htf_trend == "bearish":
            return _hold(
                f"htf-skip-long:{long_setup.origin_low:.0f}-{long_setup.higher_high:.0f}",
                f"long setup [origin={long_setup.origin_low:.2f} HH={long_setup.higher_high:.2f}] "
                f"in zone but {HTF_TIMEFRAME} trend is bearish — skipping per trend-of-trend filter",
            )
        return _entry(long=True, mark_price=mark_price,
                      stop=long_setup.stop, tp=long_setup.take_profit)

    short_setup = _detect_short_setup(candles, PIVOT_LOOKBACK)
    if short_setup and short_setup.fib_low <= mark_price <= short_setup.fib_high:
        if htf_trend == "bullish":
            return _hold(
                f"htf-skip-short:{short_setup.origin_high:.0f}-{short_setup.lower_low:.0f}",
                f"short setup [origin={short_setup.origin_high:.2f} LL={short_setup.lower_low:.2f}] "
                f"in zone but {HTF_TIMEFRAME} trend is bullish — skipping per trend-of-trend filter",
            )
        return _entry(long=False, mark_price=mark_price,
                      stop=short_setup.stop, tp=short_setup.take_profit)

    # No qualifying entry — describe what setups exist and where mark sits.
    # Dedup keys exclude live mark price so a pulling-back BTC doesn't re-log every tick;
    # the printed message includes mark for human readability.
    if long_setup is None and short_setup is None:
        return _hold("none", "no structure break detected (no HH or LL among recent pivots)")
    if long_setup and short_setup:
        return _hold(
            f"both:{long_setup.origin_low:.0f}-{long_setup.higher_high:.0f}|"
            f"{short_setup.origin_high:.0f}-{short_setup.lower_low:.0f}",
            f"both setups present; mark {mark_price:.2f} outside both zones "
            f"long=[{long_setup.fib_low:.2f}-{long_setup.fib_high:.2f}] "
            f"short=[{short_setup.fib_low:.2f}-{short_setup.fib_high:.2f}]",
        )
    if long_setup:
        return _hold(
            f"long:{long_setup.origin_low:.0f}-{long_setup.higher_high:.0f}",
            f"long setup [origin={long_setup.origin_low:.2f} HH={long_setup.higher_high:.2f}] "
            f"but mark {mark_price:.2f} outside fib zone "
            f"[{long_setup.fib_low:.2f}-{long_setup.fib_high:.2f}]",
        )
    return _hold(
        f"short:{short_setup.origin_high:.0f}-{short_setup.lower_low:.0f}",
        f"short setup [origin={short_setup.origin_high:.2f} LL={short_setup.lower_low:.2f}] "
        f"but mark {mark_price:.2f} outside fib zone "
        f"[{short_setup.fib_low:.2f}-{short_setup.fib_high:.2f}]",
    )


def _entry(*, long: bool, mark_price: float, stop: float, tp: float) -> Decision:
    """Build an entry Decision sized for 3% equity risk on the stop. HOLDs if
    the stop is too tight to size within the 20× leverage cap."""
    stop_dist_pct = abs(mark_price - stop) / mark_price * 100.0
    tp_dist_pct = abs(tp - mark_price) / mark_price * 100.0

    sized = _size_for_risk(stop_dist_pct)
    if sized is None:
        log.info("entry rejected: stop too tight (%.3f%%) for max leverage %d×",
                 stop_dist_pct, MAX_LEVERAGE)
        if _api is not None:
            _api.log_decision(
                action="hold",
                reason=f"entry rejected: stop too tight ({stop_dist_pct:.3f}%) for max leverage {MAX_LEVERAGE}×",
                payload={"side": "long" if long else "short", "mark": mark_price,
                         "stop": stop, "stop_dist_pct": stop_dist_pct, "max_lev": MAX_LEVERAGE},
            )
        return Decision(Action.HOLD)
    size_pct, leverage = sized

    # Remember entry context for the breakeven-trail logic.
    memory.entry_price = mark_price
    memory.original_stop_pct = stop_dist_pct
    memory.moved_to_breakeven = False

    side = "long" if long else "short"
    if _api is not None:
        _api.log_decision(
            action=f"open_{side}",
            reason=(
                f"open {side} @ {mark_price:.2f}, stop {stop:.2f} ({stop_dist_pct:.2f}%), "
                f"tp {tp:.2f} ({tp_dist_pct:.2f}%), sized {size_pct:.1f}% × {leverage}×"
            )[:280],
            payload={"side": side, "entry": mark_price, "stop": stop, "tp": tp,
                     "stop_dist_pct": stop_dist_pct, "tp_dist_pct": tp_dist_pct,
                     "size_pct": size_pct, "leverage": leverage},
        )

    return Decision(
        action=Action.OPEN_LONG if long else Action.OPEN_SHORT,
        size_pct=size_pct,
        leverage=leverage,
        stop_pct=stop_dist_pct,
        take_profit_pct=tp_dist_pct,
    )


def _maybe_breakeven_trail(snap: Snapshot, mark_price: float) -> None:
    """Once price has moved >= 1R in our favor, move the local stop to entry.
    A trade that's been BE-trailed has zero further drawdown contribution."""
    if memory.moved_to_breakeven:
        return
    if memory.entry_price is None or memory.original_stop_pct is None:
        return
    if snap.open_position is None:
        return

    one_r = memory.entry_price * (memory.original_stop_pct / 100.0)
    side = snap.open_position.get("side")

    if side == "long" and mark_price - memory.entry_price >= one_r:
        memory.stop_price = memory.entry_price
        memory.moved_to_breakeven = True
        log.info("BE TRAIL (long) — stop moved to entry %.2f (mark %.2f, 1R=%.2f)",
                 memory.entry_price, mark_price, one_r)
    elif side == "short" and memory.entry_price - mark_price >= one_r:
        memory.stop_price = memory.entry_price
        memory.moved_to_breakeven = True
        log.info("BE TRAIL (short) — stop moved to entry %.2f (mark %.2f, 1R=%.2f)",
                 memory.entry_price, mark_price, one_r)


# ---------- Plumbing (HMAC client + main loop) ----------

class BotPit:
    def __init__(self, base: str, pubkey: str, secret: str):
        self.base = base.rstrip("/")
        self.pubkey = pubkey
        self.secret = secret.encode("utf-8")
        self.session = requests.Session()

    def _sign(self, body: str) -> Dict[str, str]:
        t = int(time.time() * 1000)
        mac = hmac.new(self.secret, f"{t}.{body}".encode("utf-8"), hashlib.sha256)
        return {
            "Agent-Arena-Key": self.pubkey,
            "Agent-Arena-Signature": f"t={t},v1={mac.hexdigest()}",
        }

    def tournament(self) -> dict:
        r = self.session.get(
            f"{self.base}/api/v1/tv/tournament",
            headers={**self._sign(""), "Content-Type": "application/json"},
            timeout=8,
        )
        r.raise_for_status()
        return r.json()

    def state(self) -> dict:
        r = self.session.get(
            f"{self.base}/api/v1/tv/state",
            headers={**self._sign(""), "Content-Type": "application/json"},
            timeout=8,
        )
        r.raise_for_status()
        return r.json()

    def send_signal(self, *, side: str, pair: str, size_pct: float, leverage: int) -> dict:
        body_dict = {
            "nonce": int(time.time() * 1000),
            "pair": pair,
            "side": side,
            "order_type": "market",
            "size": {"mode": "pct_equity", "value": size_pct},
            "leverage": leverage,
        }
        body = json.dumps(body_dict, separators=(",", ":"))
        r = self.session.post(
            f"{self.base}/api/v1/signals",
            data=body,
            headers={**self._sign(body), "Content-Type": "application/json"},
            timeout=8,
        )
        if r.status_code >= 400:
            log.warning("signal rejected: %s %s", r.status_code, r.text[:240])
            return {"status": "rejected", "http": r.status_code, "raw": r.text}
        return r.json()

    def log_decision(self, *, action: str, reason: str,
                     payload: Optional[Dict[str, Any]] = None) -> None:
        """Append a decision-trace record to /api/v1/decisions. Lets dashboards
        render WHY the bot chose what it chose without recomputing the strategy.
        Fire-and-forget — failures are logged but don't break the tick.
        Platform caps to last 100 rows per agent automatically."""
        body_dict: Dict[str, Any] = {"action": action, "reason": reason}
        if payload is not None:
            body_dict["payload"] = payload
        body = json.dumps(body_dict, separators=(",", ":"))
        try:
            r = self.session.post(
                f"{self.base}/api/v1/decisions",
                data=body,
                headers={**self._sign(body), "Content-Type": "application/json"},
                timeout=4,
            )
            if r.status_code >= 400:
                log.warning("decision rejected: %s %s", r.status_code, r.text[:200])
        except requests.RequestException as e:
            log.warning("decision log failed: %s", e)


# Module-level reference to the BotPit client so strategy helpers (`_hold`,
# `_entry`) can fire decision-trace records without threading the api object
# through every signature. Set in `run()`; None during the validator's
# import-time smoke test.
_api: Optional["BotPit"] = None


BINANCE_MARK = "https://fapi.binance.com/fapi/v1/premiumIndex"


def get_mark_price(pair: str) -> float:
    symbol = pair.replace("-", "")
    r = requests.get(BINANCE_MARK, params={"symbol": symbol}, timeout=5)
    r.raise_for_status()
    return float(r.json()["markPrice"])


def watch_stops(snap: Snapshot, mark_price: float) -> Optional[Decision]:
    if snap.open_position is None:
        return None
    side = snap.open_position["side"]
    if memory.stop_price is not None:
        if side == "long" and mark_price <= memory.stop_price:
            reason = (
                f"BE close (long) — mark {mark_price:.2f} ≤ entry-stop {memory.stop_price:.2f}"
                if memory.moved_to_breakeven
                else f"stop hit (long) — mark {mark_price:.2f} ≤ stop {memory.stop_price:.2f}"
            )
            log.info(reason)
            memory.last_close_reason = reason
            return Decision(Action.CLOSE)
        if side == "short" and mark_price >= memory.stop_price:
            reason = (
                f"BE close (short) — mark {mark_price:.2f} ≥ entry-stop {memory.stop_price:.2f}"
                if memory.moved_to_breakeven
                else f"stop hit (short) — mark {mark_price:.2f} ≥ stop {memory.stop_price:.2f}"
            )
            log.info(reason)
            memory.last_close_reason = reason
            return Decision(Action.CLOSE)
    if memory.take_profit_price is not None:
        if side == "long" and mark_price >= memory.take_profit_price:
            reason = f"TP hit (long) — mark {mark_price:.2f} ≥ tp {memory.take_profit_price:.2f}"
            log.info(reason)
            memory.last_close_reason = reason
            return Decision(Action.CLOSE)
        if side == "short" and mark_price <= memory.take_profit_price:
            reason = f"TP hit (short) — mark {mark_price:.2f} ≤ tp {memory.take_profit_price:.2f}"
            log.info(reason)
            memory.last_close_reason = reason
            return Decision(Action.CLOSE)
    return None


def build_snapshot(api: BotPit, pair: str, rules: dict) -> Snapshot:
    s = api.state()
    open_pos = next((p for p in s["positions"] if p["pair"] == pair), None)
    last_fill_price = None
    if open_pos:
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
            log.info("decide() wants %s but already %s; close first.",
                     decision.action.value, snap.open_position["side"])
            return
        side = "long" if decision.action == Action.OPEN_LONG else "short"
        resp = api.send_signal(side=side, pair=pair, size_pct=decision.size_pct, leverage=decision.leverage)
        log.info("OPEN %s sized=%.2f%% lev=%dx -> %s",
                 decision.action.value, decision.size_pct, decision.leverage, resp.get("status"))
        try:
            mark = get_mark_price(pair)
            if decision.action == Action.OPEN_LONG:
                memory.stop_price = mark * (1 - decision.stop_pct / 100)
                memory.take_profit_price = mark * (1 + decision.take_profit_pct / 100)
            else:
                memory.stop_price = mark * (1 + decision.stop_pct / 100)
                memory.take_profit_price = mark * (1 - decision.take_profit_pct / 100)
            log.info("stop @ %.2f, tp @ %.2f", memory.stop_price, memory.take_profit_price)
        except Exception as e:
            log.warning("couldn't set client-side stop: %s", e)
        return
    if decision.action == Action.CLOSE:
        if snap.open_position is None:
            return
        resp = api.send_signal(side="close", pair=pair, size_pct=100, leverage=1)
        log.info("CLOSE sent -> %s", resp.get("status"))
        if _api is not None:
            close_reason = memory.last_close_reason or "close (manual or unknown trigger)"
            _api.log_decision(
                action="close",
                reason=close_reason[:280],
                payload={"pair": pair, "side_closed": snap.open_position.get("side"),
                         "entry": memory.entry_price,
                         "moved_to_breakeven": memory.moved_to_breakeven},
            )
        memory.stop_price = None
        memory.take_profit_price = None
        memory.entry_price = None
        memory.original_stop_pct = None
        memory.moved_to_breakeven = False
        memory.last_close_reason = None


def run() -> None:
    # Cred check deferred from import-time so the validator's smoke test (which
    # imports the module without the env vars set) doesn't crash. See R4-2.
    if not PUBKEY or not SECRET:
        sys.exit(
            "BOTPIT_AGENT_PUBKEY / BOTPIT_AGENT_SECRET not set. "
            "Paste the keypair from https://www.botpit.io/agents/<your-agent-id>."
        )

    api = BotPit(API_BASE, PUBKEY, SECRET)
    global _api
    _api = api  # let _hold/_entry helpers fire decision-trace records
    log.info("The Stuber starting up against %s", API_BASE)
    t = api.tournament()
    rules, tournament = t["rules"], t["tournament"]
    log.info("tournament: %s (ends %s)", tournament["name"], tournament["ends_at"])
    log.info("rules: leverage_cap=%dx allowed_pairs=%s starting_equity=$%s",
             rules["leverage_cap"], rules["allowed_pairs"], rules["starting_equity_usd"])
    if PAIR not in rules["allowed_pairs"]:
        sys.exit(f"PAIR={PAIR} not in allowed_pairs {rules['allowed_pairs']}; set BOTPIT_PAIR.")

    last_heartbeat = 0.0
    HEARTBEAT_EVERY = 60

    while True:
        try:
            snap = build_snapshot(api, PAIR, rules)
            mark = get_mark_price(PAIR)
            stop_decision = watch_stops(snap, mark)
            if stop_decision:
                apply_decision(api, stop_decision, snap, PAIR)
                snap = build_snapshot(api, PAIR, rules)
            decision = decide(snap, mark)
            apply_decision(api, decision, snap, PAIR)
            now = time.time()
            if now - last_heartbeat > HEARTBEAT_EVERY:
                pos_str = (
                    f"{snap.open_position['side']} {snap.open_position['size_units']:.4f} "
                    f"{PAIR} @ ${snap.open_position['entry_price']:.2f}"
                    if snap.open_position else "flat"
                )
                log.info("hb: equity=$%.2f return=%+.2f%% dd=%.2f%% pos=[%s] mark=%.2f",
                         snap.equity_usd, snap.return_pct, snap.drawdown_pct, pos_str, mark)
                last_heartbeat = now
        except requests.RequestException as e:
            log.warning("network blip: %s -- backing off 5s", e)
            time.sleep(5)
            continue
        except Exception as e:
            log.exception("unexpected error: %s", e)
            time.sleep(5)
            continue
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    run()

"""
BotPit minimal-but-safe Python bot — HMAC code-bot path.

Spec: https://www.botpit.io/llms.txt
"""

from __future__ import annotations

import os
import sys
import time
import enum
import json
import hmac
import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

API_BASE = os.getenv("BOTPIT_API_BASE", "https://www.botpit.io")
PUBKEY = os.environ.get("BOTPIT_AGENT_PUBKEY")
SECRET = os.environ.get("BOTPIT_AGENT_SECRET")
PAIR = os.getenv("BOTPIT_PAIR", "BTC-USDT")
TICK_SECONDS = int(os.getenv("BOTPIT_TICK_SECONDS", "10"))

# Note: env-var validation is deferred to run() so the module can be
# imported without credentials (e.g. by CI validators or unit tests).
# The bot only fails fast when you actually try to start it.

logging.basicConfig(format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S", level=logging.INFO)
log = logging.getLogger("bot")


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
        r = self.session.get(f"{self.base}/api/v1/tv/tournament",
                             headers={**self._sign(""), "Content-Type": "application/json"}, timeout=8)
        r.raise_for_status()
        return r.json()

    def state(self) -> dict:
        r = self.session.get(f"{self.base}/api/v1/tv/state",
                             headers={**self._sign(""), "Content-Type": "application/json"}, timeout=8)
        r.raise_for_status()
        return r.json()

    def send_signal(self, *, side: str, pair: str, size_pct: float, leverage: int,
                    nonce: Optional[int] = None) -> dict:
        body_dict = {
            "nonce": nonce if nonce is not None else int(time.time() * 1000),
            "pair": pair, "side": side, "order_type": "market",
            "size": {"mode": "pct_equity", "value": size_pct}, "leverage": leverage,
        }
        body = json.dumps(body_dict, separators=(",", ":"))
        r = self.session.post(f"{self.base}/api/v1/signals", data=body,
                              headers={**self._sign(body), "Content-Type": "application/json"}, timeout=8)
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
            r = self.session.post(f"{self.base}/api/v1/decisions", data=body,
                                  headers={**self._sign(body), "Content-Type": "application/json"}, timeout=4)
            if r.status_code >= 400:
                log.warning("decision rejected: %s %s", r.status_code, r.text[:200])
        except requests.RequestException as e:
            log.warning("decision log failed: %s", e)


BINANCE_MARK = "https://fapi.binance.com/fapi/v1/premiumIndex"

def get_mark_price(pair: str) -> float:
    symbol = pair.replace("-", "")
    r = requests.get(BINANCE_MARK, params={"symbol": symbol}, timeout=5)
    r.raise_for_status()
    return float(r.json()["markPrice"])


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
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None


memory = StopMemory()


def decide(snap: Snapshot, mark_price: float) -> Decision:
    """PLACEHOLDER STRATEGY — replace with your own.

    Examples to ask your LLM for:
      - "Open long when mark price drops 1% from the 60-tick rolling high.
         Close when up 0.5% or down 1%."
      - "Buy when RSI(14) crosses below 30, close when it crosses above 70."

    Return Decision(Action.HOLD) | Decision(Action.OPEN_LONG, ...) |
    Decision(Action.OPEN_SHORT, ...) | Decision(Action.CLOSE).
    """
    return Decision(Action.HOLD)


def watch_stops(snap: Snapshot, mark_price: float) -> Optional[Decision]:
    if snap.open_position is None:
        return None
    side = snap.open_position["side"]
    if memory.stop_price is not None:
        if side == "long" and mark_price <= memory.stop_price:
            log.info("STOP HIT (long) — mark %.2f <= stop %.2f", mark_price, memory.stop_price)
            return Decision(Action.CLOSE)
        if side == "short" and mark_price >= memory.stop_price:
            log.info("STOP HIT (short) — mark %.2f >= stop %.2f", mark_price, memory.stop_price)
            return Decision(Action.CLOSE)
    if memory.take_profit_price is not None:
        if side == "long" and mark_price >= memory.take_profit_price:
            log.info("TP HIT (long) — mark %.2f >= tp %.2f", mark_price, memory.take_profit_price)
            return Decision(Action.CLOSE)
        if side == "short" and mark_price <= memory.take_profit_price:
            log.info("TP HIT (short) — mark %.2f <= tp %.2f", mark_price, memory.take_profit_price)
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
        log.info("OPEN %s sent -> %s", decision.action.value, resp.get("status"))
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
            return
        resp = api.send_signal(side="close", pair=pair, size_pct=100, leverage=1)
        log.info("CLOSE sent -> %s", resp.get("status"))
        memory.stop_price = None
        memory.take_profit_price = None


def run() -> None:
    if not PUBKEY or not SECRET:
        sys.exit(
            "BOTPIT_AGENT_PUBKEY / BOTPIT_AGENT_SECRET not set. "
            "Copy .env.example to .env and paste the keypair from "
            "https://www.botpit.io/agents/<your-agent-id>."
        )
    api = BotPit(API_BASE, PUBKEY, SECRET)
    log.info("starting up against %s", API_BASE)
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
                    f"{snap.open_position['side']} {snap.open_position['size_units']:.4f} {PAIR} @ ${snap.open_position['entry_price']:.2f}"
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

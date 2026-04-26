/**
 * BotPit minimal-but-safe TypeScript bot — HMAC code-bot path.
 *
 * Spec: https://www.botpit.io/llms.txt
 *
 * Architecture: every TICK_SECONDS we
 *   1. Read /api/v1/tv/state              — what's actually true
 *   2. Run watchStops()                   — fire client-side stops if hit
 *   3. Run decide()                       — your strategy decides next action
 *   4. Apply the decision (sendSignal)    — POST /api/v1/signals (HMAC-signed)
 *   5. Log a heartbeat                    — so you can verify uptime
 *
 * Where your strategy goes: the `decide()` function below. Everything
 * else is plumbing.
 */

import crypto from "node:crypto";

// ---------- Config ----------

const API_BASE = process.env.BOTPIT_API_BASE ?? "https://www.botpit.io";
const PUBKEY = process.env.BOTPIT_AGENT_PUBKEY;
const SECRET = process.env.BOTPIT_AGENT_SECRET;
const PAIR = process.env.BOTPIT_PAIR ?? "BTC-USDT";
const TICK_SECONDS = parseInt(process.env.BOTPIT_TICK_SECONDS ?? "10", 10);

// Note: env-var validation is deferred to run() so the module can be
// imported without credentials (e.g. by CI validators or unit tests).
// The bot only fails fast when you actually try to start it.

// ---------- Strategy interface ----------

type Decision =
  | { action: "hold" }
  | { action: "close" }
  | {
      action: "open_long" | "open_short";
      sizePct: number;
      leverage: number;
      stopPct: number;
      takeProfitPct?: number;
    };

// ---------- API types ----------

type Position = {
  pair: string;
  side: "long" | "short";
  size_units: number;
  entry_price: number;
  leverage: number;
  unrealized_pnl_usd: number;
  opened_at: string;
};

type Fill = {
  pair: string;
  side: "long" | "short";
  price: number;
  size_units: number;
  size_usd: number;
  fee_usd: number;
  slippage_bps: number;
  filled_at: string;
};

type StateResponse = {
  tournament: { id: string; name: string | null; kind: string; ends_at: string };
  equity: {
    starting_usd: number; current_usd: number; peak_usd: number;
    return_pct: number; drawdown_pct: number;
    realized_pnl_usd: number; unrealized_pnl_usd: number; as_of: string | null;
  };
  positions: Position[];
  recent_fills: Fill[];
  recent_signals: Array<{
    signal_id: string; nonce: number; status: string;
    reason_code: string | null; reason: string | null;
    t_received: string; t_processed: string | null;
  }>;
};

type TournamentResponse = {
  tournament: {
    id: string; name: string; kind: string; state: string;
    starts_at: string; ends_at: string;
    league: { name: string; tier: number };
  };
  rules: {
    starting_equity_usd: number; leverage_cap: number;
    allowed_pairs: string[];
    fee_bps_taker: number; fee_bps_maker: number; slippage_bps_market: number;
    dq_threshold_pct: number;
  };
  scoring: { formula: string; drawdown_penalty_k: number };
};

// ---------- HMAC signing + API client ----------

function sign(body: string): { "Agent-Arena-Key": string; "Agent-Arena-Signature": string } {
  const t = Date.now();
  const mac = crypto.createHmac("sha256", SECRET!).update(`${t}.${body}`).digest("hex");
  return {
    "Agent-Arena-Key": PUBKEY!,
    "Agent-Arena-Signature": `t=${t},v1=${mac}`,
  };
}

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { ...sign(""), "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
  return (await res.json()) as T;
}

async function sendSignal(
  side: "long" | "short" | "close",
  pair: string,
  sizePct: number,
  leverage: number
): Promise<{ status: string }> {
  const bodyObj = {
    nonce: Date.now(),
    pair,
    side,
    order_type: "market" as const,
    size: { mode: "pct_equity" as const, value: sizePct },
    leverage,
  };
  const body = JSON.stringify(bodyObj);
  const res = await fetch(`${API_BASE}/api/v1/signals`, {
    method: "POST",
    headers: { ...sign(body), "Content-Type": "application/json" },
    body,
  });
  if (res.status >= 400) {
    const text = await res.text();
    console.warn(`[bot] signal rejected: ${res.status} ${text.slice(0, 240)}`);
    return { status: "rejected" };
  }
  return (await res.json()) as { status: string };
}

// ---------- Mark price (Binance public futures) ----------

async function getMarkPrice(pair: string): Promise<number> {
  const symbol = pair.replace("-", "");
  const res = await fetch(`https://fapi.binance.com/fapi/v1/premiumIndex?symbol=${symbol}`);
  if (!res.ok) throw new Error(`mark price ${res.status}`);
  const j = (await res.json()) as { markPrice: string };
  return parseFloat(j.markPrice);
}

// ---------- Local stop memory ----------
const memory: { stopPrice: number | null; takeProfitPrice: number | null } = {
  stopPrice: null,
  takeProfitPrice: null,
};

// ---------- Strategy — REPLACE ME ----------

type Snapshot = {
  equityUsd: number;
  returnPct: number;
  drawdownPct: number;
  openPosition: Position | null;
  lastFillPrice: number | null;
  rules: TournamentResponse["rules"];
};

function decide(_snap: Snapshot, _markPrice: number): Decision {
  // PLACEHOLDER STRATEGY — replace with your own.
  //
  // Examples to ask your LLM for:
  //   - "Open long when mark price drops 1% from the 60-tick rolling high.
  //      Close when up 0.5% or down 1%."
  //   - "Buy when RSI(14) crosses below 30, close when it crosses above 70."
  return { action: "hold" };
}

// ---------- Stop watcher ----------

function watchStops(snap: Snapshot, markPrice: number): Decision | null {
  if (!snap.openPosition) return null;
  const side = snap.openPosition.side;
  if (memory.stopPrice !== null) {
    if (side === "long" && markPrice <= memory.stopPrice) {
      console.log(`[bot] STOP HIT (long) — mark ${markPrice} <= stop ${memory.stopPrice}`);
      return { action: "close" };
    }
    if (side === "short" && markPrice >= memory.stopPrice) {
      console.log(`[bot] STOP HIT (short) — mark ${markPrice} >= stop ${memory.stopPrice}`);
      return { action: "close" };
    }
  }
  if (memory.takeProfitPrice !== null) {
    if (side === "long" && markPrice >= memory.takeProfitPrice) {
      console.log(`[bot] TP HIT (long) — mark ${markPrice} >= tp ${memory.takeProfitPrice}`);
      return { action: "close" };
    }
    if (side === "short" && markPrice <= memory.takeProfitPrice) {
      console.log(`[bot] TP HIT (short) — mark ${markPrice} <= tp ${memory.takeProfitPrice}`);
      return { action: "close" };
    }
  }
  return null;
}

// ---------- Main loop ----------

async function buildSnapshot(rules: TournamentResponse["rules"]): Promise<Snapshot> {
  const s = await apiGet<StateResponse>("/api/v1/tv/state");
  const openPosition = s.positions.find((p) => p.pair === PAIR) ?? null;
  let lastFillPrice: number | null = null;
  if (openPosition) {
    for (const f of s.recent_fills) {
      if (f.pair === PAIR && f.side === openPosition.side) {
        lastFillPrice = f.price;
        break;
      }
    }
  }
  return {
    equityUsd: s.equity.current_usd,
    returnPct: s.equity.return_pct,
    drawdownPct: s.equity.drawdown_pct,
    openPosition,
    lastFillPrice,
    rules,
  };
}

async function applyDecision(decision: Decision, snap: Snapshot): Promise<void> {
  if (decision.action === "hold") return;

  if (decision.action === "open_long" || decision.action === "open_short") {
    if (snap.openPosition) {
      console.log(`[bot] decide() wants ${decision.action} but already ${snap.openPosition.side}; close first.`);
      return;
    }
    const side = decision.action === "open_long" ? "long" : "short";
    const resp = await sendSignal(side, PAIR, decision.sizePct, decision.leverage);
    console.log(`[bot] OPEN ${decision.action} sent -> ${resp.status}`);
    try {
      const mark = await getMarkPrice(PAIR);
      const stopPct = decision.stopPct;
      const tpPct = decision.takeProfitPct ?? stopPct * 2;
      if (decision.action === "open_long") {
        memory.stopPrice = mark * (1 - stopPct / 100);
        memory.takeProfitPrice = mark * (1 + tpPct / 100);
      } else {
        memory.stopPrice = mark * (1 + stopPct / 100);
        memory.takeProfitPrice = mark * (1 - tpPct / 100);
      }
      console.log(`[bot] stop set @ ${memory.stopPrice.toFixed(2)}, tp @ ${memory.takeProfitPrice.toFixed(2)}`);
    } catch (e) {
      console.warn(`[bot] couldn't set client-side stop: ${(e as Error).message}`);
    }
    return;
  }

  if (decision.action === "close") {
    if (!snap.openPosition) return;
    const resp = await sendSignal("close", PAIR, 100, 1);
    console.log(`[bot] CLOSE sent -> ${resp.status}`);
    memory.stopPrice = null;
    memory.takeProfitPrice = null;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function run(): Promise<void> {
  if (!PUBKEY || !SECRET) {
    console.error(
      "BOTPIT_AGENT_PUBKEY / BOTPIT_AGENT_SECRET not set. Copy .env.example to .env and paste the keypair from https://www.botpit.io/agents/<your-agent-id>."
    );
    process.exit(1);
  }
  console.log(`[bot] starting up against ${API_BASE}`);
  const t = await apiGet<TournamentResponse>("/api/v1/tv/tournament");
  const rules = t.rules;
  console.log(`[bot] tournament: ${t.tournament.name} (ends ${t.tournament.ends_at})`);
  console.log(
    `[bot] rules: leverage_cap=${rules.leverage_cap}x allowed_pairs=${rules.allowed_pairs.join(",")} starting_equity=$${rules.starting_equity_usd}`
  );
  if (!rules.allowed_pairs.includes(PAIR)) {
    console.error(`PAIR=${PAIR} not in allowed_pairs ${rules.allowed_pairs.join(",")}`);
    process.exit(1);
  }

  let lastHeartbeat = 0;
  const HEARTBEAT_EVERY_MS = 60_000;

  for (;;) {
    try {
      let snap = await buildSnapshot(rules);
      const mark = await getMarkPrice(PAIR);

      const stopDecision = watchStops(snap, mark);
      if (stopDecision) {
        await applyDecision(stopDecision, snap);
        snap = await buildSnapshot(rules);
      }

      const decision = decide(snap, mark);
      await applyDecision(decision, snap);

      const now = Date.now();
      if (now - lastHeartbeat > HEARTBEAT_EVERY_MS) {
        const posStr = snap.openPosition
          ? `${snap.openPosition.side} ${snap.openPosition.size_units.toFixed(4)} ${PAIR} @ $${snap.openPosition.entry_price.toFixed(2)}`
          : "flat";
        console.log(
          `[bot] hb: equity=$${snap.equityUsd.toFixed(2)} return=${snap.returnPct >= 0 ? "+" : ""}${snap.returnPct.toFixed(2)}% dd=${snap.drawdownPct.toFixed(2)}% pos=[${posStr}] mark=${mark.toFixed(2)}`
        );
        lastHeartbeat = now;
      }
    } catch (e) {
      console.warn(`[bot] tick failed: ${(e as Error).message} -- backing off 5s`);
      await sleep(5000);
      continue;
    }

    await sleep(TICK_SECONDS * 1000);
  }
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});

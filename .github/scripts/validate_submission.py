"""
Submission validator for botpit-bot-starter.

Run: python .github/scripts/validate_submission.py submissions/<username>

Checks (intentionally narrow — quality + safety, not strategy evaluation):
  - folder name is lowercase alphanumeric + dashes
  - bot.py (or bot.ts) present and under 50KB
  - total folder under 500KB
  - STRATEGY.md present and non-empty
  - python: no banned imports (subprocess, os.system, eval, exec, requests
      to non-allowlisted hosts via static AST scan)
  - python: bot.py imports without error in a sandboxed env
  - python: decide() exists and is callable with a fake snapshot
  - typescript: skipped here (a separate Node validator can run on
    .ts files; for v1 we only auto-validate Python)

Exit code 0 = pass, 1 = fail.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

MAX_BOT_BYTES = 50 * 1024
MAX_FOLDER_BYTES = 500 * 1024

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Static-AST banned-import list. Keeps the surface narrow without
# trying to be a full sandbox — the runtime in v2 will handle real isolation.
BANNED_IMPORTS = {
    "subprocess",
    "ctypes",
    "socket",
    "shutil",
    "pty",
    "telnetlib",
    "ftplib",
    "paramiko",
    "fabric",
    "pickle",
    "marshal",
}
BANNED_CALLS = {"eval", "exec", "compile", "__import__", "open"}
# Network is allowed only to BotPit + Binance public futures
ALLOWED_NETWORK_HOSTS = {
    "www.botpit.io",
    "botpit.io",
    "fapi.binance.com",
}


def fail(msg: str) -> None:
    print(f"::error::{msg}")
    sys.exit(1)


def info(msg: str) -> None:
    print(f"  · {msg}")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: validate_submission.py <submissions/username>")
    folder = Path(sys.argv[1]).resolve()

    if not folder.is_dir():
        fail(f"{folder} is not a directory")

    # username check
    username = folder.name
    if username.startswith("EXAMPLE"):
        info(f"skipping example folder {username}")
        sys.exit(0)
    if not USERNAME_RE.match(username):
        fail(
            f"folder name '{username}' must be lowercase alphanumeric + dashes "
            "(e.g. 'jane-doe', not 'JaneDoe')"
        )
    info(f"username: {username}")

    # folder size
    total = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
    if total > MAX_FOLDER_BYTES:
        fail(f"folder is {total} bytes; max {MAX_FOLDER_BYTES}")
    info(f"folder size: {total} bytes")

    # STRATEGY.md
    strategy = folder / "STRATEGY.md"
    if not strategy.exists() or strategy.stat().st_size == 0:
        fail("STRATEGY.md is missing or empty — explain what your bot does")
    info("STRATEGY.md present")

    # detect bot file
    bot_py = folder / "bot.py"
    bot_ts = folder / "bot.ts"
    if bot_py.exists():
        validate_python_bot(bot_py)
    elif bot_ts.exists():
        info("typescript submission detected — skipping deep validation in v1")
    else:
        fail("no bot.py or bot.ts in folder")

    print("::notice::submission validates ✓")


def validate_python_bot(bot_py: Path) -> None:
    size = bot_py.stat().st_size
    if size > MAX_BOT_BYTES:
        fail(f"bot.py is {size} bytes; max {MAX_BOT_BYTES}")
    info(f"bot.py size: {size} bytes")

    src = bot_py.read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        fail(f"bot.py syntax error: {e}")

    # AST scan — banned imports and calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                root = n.name.split(".")[0]
                if root in BANNED_IMPORTS:
                    fail(f"banned import: {n.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in BANNED_IMPORTS:
                fail(f"banned import: from {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BANNED_CALLS:
                fail(f"banned call: {node.func.id}()")
    info("static checks passed")

    # Smoke test: import + call decide() with a fake snapshot
    # The starter bot calls sys.exit if BOTPIT_TV_TOKEN is missing — set a fake one.
    os.environ["BOTPIT_TV_TOKEN"] = "aatv_" + "0" * 64
    spec = importlib.util.spec_from_file_location("submission_bot", bot_py)
    if spec is None or spec.loader is None:
        fail("couldn't load bot.py")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so internal references resolve correctly.
    sys.modules["submission_bot"] = module
    try:
        spec.loader.exec_module(module)
    except SystemExit as e:
        fail(f"bot.py exited at import time: {e}")
    except Exception as e:
        fail(f"bot.py raised at import: {type(e).__name__}: {e}")
    info("module imports cleanly")

    decide = getattr(module, "decide", None)
    if not callable(decide):
        fail("bot.py must export a callable `decide(snap, mark_price)`")
    info("decide() found")

    fake_snap = SimpleNamespace(
        equity_usd=100_000.0,
        return_pct=0.0,
        drawdown_pct=0.0,
        open_position=None,
        last_fill_price=None,
        pair_config={
            "starting_equity_usd": 100_000,
            "leverage_cap": 20,
            "allowed_pairs": ["BTC-USDT", "ETH-USDT", "SOL-USDT", "PAXG-USDT"],
        },
    )
    try:
        decision = decide(fake_snap, 60_000.0)
    except Exception as e:
        fail(f"decide() raised on smoke test: {type(e).__name__}: {e}")

    if decision is None:
        fail("decide() returned None — must return a Decision dataclass")
    info(f"smoke test ok: decide() returned {decision!r}")


if __name__ == "__main__":
    main()

"""
Persistence helpers (atomic JSON), money math (Decimal), history I/O, validation,
and the payer selection logic with configurable tie strategies.

Fairness model:
- `balances[name]` = cumulative amount a person has paid so far.
- The next payer is the one with the **lowest** cumulative paid total.
- If multiple are tied, tie-breaker is configurable:
    * least_recent : never-paid wins; otherwise the one who paid longer ago wins
    * alpha        : alphabetical
    * random       : random among ties
    * round_robin  : cycle among ties in alphabetical order, based on who paid most recently
"""

from __future__ import annotations

import csv
import json
import os
import secrets
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple, Optional

# ---- File locations (relative to backend/) ----
PRICES_FILE = "data/prices.json"
BALANCES_FILE = "data/balances.json"
HISTORY_FILE = "data/history.csv"

# ---- Money precision ----
CENTS = Decimal("0.01")


# ============================================================================
# Money helpers
# ============================================================================

def D(x) -> Decimal:
    """Create Decimal from any numeric/string input in a safe way."""
    return Decimal(str(x))


def money(x: Decimal) -> Decimal:
    """Quantize to 2 decimal places using bankers' rounding."""
    return x.quantize(CENTS, rounding=ROUND_HALF_UP)


# ============================================================================
# Atomic JSON I/O
# ============================================================================

def load_json(path: str, default):
    """Load JSON or return `default` if file does not exist."""
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_atomic(path: str, data):
    """
    Atomically write JSON to disk.
    - Write to a temporary file in the same directory
    - fsync to ensure bytes hit disk
    - os.replace to swap into place (atomic on POSIX)
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dir_ = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=dir_, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        # Best-effort cleanup if something went wrong after write
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


# Back-compat alias (some modules may import save_json)
save_json = save_json_atomic


# ============================================================================
# History helpers (CSV with header)
# ============================================================================

def ensure_history(path: str):
    """Create the CSV history file with header if it does not exist."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["timestamp", "payer", "total_cost", "people"])


def append_history_row(path: str, timestamp: str, payer: str, total_cost: Decimal, people: List[str]):
    """Append a single round to history (timestamp ISO, payer name, cost, people pipe-separated)."""
    ensure_history(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([timestamp, payer, f"{money(total_cost):.2f}", "|".join(people)])


def read_history(path: str) -> List[Dict]:
    """
    Read entire history into a list of dicts:
    {timestamp:str, payer:str, total_cost:float, people:List[str]}
    """
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            out.append({
                "timestamp": row["timestamp"],
                "payer": row["payer"],
                "total_cost": float(row["total_cost"]) if row["total_cost"] else 0.0,
                "people": row["people"].split("|") if row["people"] else [],
            })
    return out


def reset_history(path: str):
    """Truncate history to just the header row."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp", "payer", "total_cost", "people"])


def now_iso() -> str:
    """Current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# Normalizers (convert floats to Decimals, quantized)
# ============================================================================

def normalize_prices(raw: Dict[str, float]) -> Dict[str, Decimal]:
    """Normalize raw price map (float or str) -> Decimal(2dp)."""
    return {k: money(D(v)) for k, v in raw.items()}


def normalize_balances(raw: Dict[str, float]) -> Dict[str, Decimal]:
    """Normalize raw balance map (float or str) -> Decimal(2dp)."""
    return {k: money(D(v)) for k, v in raw.items()}


# ============================================================================
# Core computation
# ============================================================================

def compute_total_cost(prices: Dict[str, Decimal], people: List[str]) -> Tuple[Decimal, List[str]]:
    """
    Compute the total bill for the given people based on their configured prices.
    Returns (total: Decimal, included_people: List[str]).
    People not present in `prices` are ignored.
    """
    included = [p for p in people if p in prices]
    total = sum((prices[p] for p in included), start=Decimal("0"))
    return money(total), included


# ============================================================================
# Tie-break utilities
# ============================================================================

def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp, accepting 'Z' and '+00:00' variations."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _last_paid_map(history: List[Dict]) -> Dict[str, Optional[datetime]]:
    """
    Map each payer to their most recent payment timestamp (or None if never).
    """
    last = {}
    for row in history or []:
        p = row.get("payer")
        t = _parse_iso(row.get("timestamp"))
        if not p or t is None:
            continue
        if (p not in last) or (t > last[p]):
            last[p] = t
    return last


def _most_recent_from_set(history: List[Dict], names: List[str]) -> Optional[str]:
    """
    Among 'names', return the one that appears most recently in history.
    If none have ever paid, return None.
    """
    name_set = set(names)
    for row in reversed(history or []):
        p = row.get("payer")
        if p in name_set:
            return p
    return None


# ============================================================================
# Selection logic (configurable ties)
# ============================================================================

def select_payer(
    balances: Dict[str, Decimal],
    candidates: List[str],
    *,
    tie_strategy: str = "least_recent",
    history: Optional[List[Dict]] = None,
    rng: Optional[secrets.SystemRandom] = None,
) -> str:
    """
    Select the next payer per fairness rule.

    Primary rule:
      - Choose the person with the **lowest cumulative balance** among `candidates`.

    Tie strategies:
      - least_recent : never-paid wins; otherwise the one who paid longer ago wins
      - alpha        : alphabetical among ties
      - random       : random among ties (seed with `rng` if desired)
      - round_robin  : among tied names (sorted), pick the next name after the most
                       recent tied payer found in history; if none, pick the first.

    Args:
      balances: {name: Decimal paid_so_far}
      candidates: subset of people considered for this round
      tie_strategy: strategy string; defaults to "least_recent"
      history: parsed history list (from read_history)
      rng: optional SystemRandom for 'random' strategy

    Returns:
      Selected payer's name.

    Raises:
      ValueError if no `candidates` are present in `balances`.
    """
    present = [c for c in candidates if c in balances]
    if not present:
        raise ValueError("No valid candidates among balances.")

    # 1) Lowest cumulative balance wins
    min_paid = min(balances[c] for c in present)
    ties = [c for c in present if balances[c] == min_paid]
    if len(ties) == 1:
        return ties[0]

    # 2) Tie-breaking
    s = (tie_strategy or "least_recent").strip().lower()
    hist = history or []

    if s == "alpha":
        return sorted(ties)[0]

    if s == "random":
        r = rng or secrets.SystemRandom()
        return r.choice(ties)

    if s == "round_robin":
        ordered = sorted(ties)
        recent = _most_recent_from_set(hist, ordered)
        if not recent:
            return ordered[0]
        i = ordered.index(recent)
        return ordered[(i + 1) % len(ordered)]

    # default: least_recent
    last = _last_paid_map(hist)

    def key(name: str):
        lp = last.get(name)                 # datetime or None
        never_rank = 0 if lp is None else 1 # never-paid first
        # older (less recent) first; final alphabetical for stability
        return (never_rank, lp or datetime.min, name)

    ties.sort(key=key)
    return ties[0]


# ============================================================================
# Validation helpers
# ============================================================================

ALLOWED_NAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ -'")

def validate_person_name(name: str) -> bool:
    """
    Valid person name = 1–40 characters of letters, space, hyphen, apostrophe.
    """
    if not isinstance(name, str):
        return False
    name = name.strip()
    if not (1 <= len(name) <= 40):
        return False
    return all(ch in ALLOWED_NAME_CHARS for ch in name)


def parse_price_to_decimal(val) -> Optional[Decimal]:
    """
    Parse input to a positive Decimal (quantized to 2 decimals), else None.
    """
    try:
        d = D(val)
        if d <= 0:
            return None
        return money(d)
    except Exception:
        return None

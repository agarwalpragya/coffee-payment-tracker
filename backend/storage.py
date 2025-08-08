
import csv
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

PRICES_FILE = "data/prices.json"
BALANCES_FILE = "data/balances.json"
HISTORY_FILE = "data/history.csv"


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_history(path: str):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "payer", "total_cost", "people"])


def compute_total_cost(prices: Dict[str, float], people: List[str]) -> Tuple[float, List[str]]:
    included = [p for p in people if p in prices]
    total = sum(float(prices[p]) for p in included)
    return total, included


def deterministic_choice(names: List[str]) -> str:
    if not names:
        raise ValueError("No candidates provided.")
    return sorted(names)[0]


def select_payer(balances: Dict[str, float], candidates: List[str]) -> str:
    present = [c for c in candidates if c in balances]
    if not present:
        raise ValueError("No valid candidates found among balances.")
    min_spent = min(balances[c] for c in present)
    tied = [c for c in present if balances[c] == min_spent]
    return deterministic_choice(tied)


def append_history_row(path: str, timestamp: str, payer: str, total_cost: float, people: List[str]):
    ensure_history(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, payer, f"{total_cost:.2f}", "|".join(people)])


def read_history(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append({
                "timestamp": row["timestamp"],
                "payer": row["payer"],
                "total_cost": float(row["total_cost"]),
                "people": row["people"].split("|") if row["people"] else []
            })
    return out


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

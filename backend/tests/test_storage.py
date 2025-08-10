"""
Unit tests for money math, selection logic, and history round trip.
Run with:  pytest -q
"""

import csv
from decimal import Decimal
from storage import (
    compute_total_cost, select_payer,
    append_history_row, read_history, money
)


def test_compute_total_cost_missing_and_empty():
    """Missing names are ignored; empty selection yields 0 total and []."""
    prices = {"A": Decimal("3.00"), "B": Decimal("7.00")}
    total, included = compute_total_cost(prices, ["A", "X"])
    assert total == Decimal("3.00")
    assert included == ["A"]

    total2, included2 = compute_total_cost(prices, [])
    assert total2 == Decimal("0.00")
    assert included2 == []


def test_select_alpha():
    """Alphabetical tie-break: Ann vs Bob tie at 5.00 → Ann."""
    balances = {"Ann": Decimal("5.00"), "Bob": Decimal("5.00"), "Zed": Decimal("6.00")}
    payer = select_payer(balances, ["Ann", "Bob", "Zed"], tie_strategy="alpha")
    assert payer == "Ann"


def test_select_least_recent_never_paid_wins(tmp_path):
    """
    In least_recent: a person who has never paid beats someone who has
    (when their balances are tied).
    """
    p = tmp_path / "h.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["timestamp", "payer", "total_cost", "people"])
        w.writerow(["2024-01-01T00:00:00+00:00", "Bob", "10.00", "Ann|Bob"])
    hist = read_history(str(p))
    balances = {"Ann": Decimal("5.00"), "Bob": Decimal("5.00")}
    assert select_payer(balances, ["Ann", "Bob"], tie_strategy="least_recent", history=hist) == "Ann"


def test_select_least_recent_older_timestamp_wins(tmp_path):
    """In least_recent: older (less recent) timestamp wins among ties."""
    p = tmp_path / "h.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["timestamp", "payer", "total_cost", "people"])
        w.writerow(["2024-01-02T00:00:00+00:00", "Ann", "10.00", "Ann|Bob"])
        w.writerow(["2024-01-03T00:00:00+00:00", "Bob", "10.00", "Ann|Bob"])
    hist = read_history(str(p))
    balances = {"Ann": Decimal("5.00"), "Bob": Decimal("5.00")}
    assert select_payer(balances, ["Ann", "Bob"], tie_strategy="least_recent", history=hist) == "Ann"


def test_select_round_robin(tmp_path):
    """
    Round-robin among ties: suppose ties are Ann,Bob,Zed (sorted).
    If most recent tied payer is Ann, next should be Bob (cyclic).
    """
    p = tmp_path / "h.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["timestamp", "payer", "total_cost", "people"])
        w.writerow(["2024-01-05T00:00:00+00:00", "Ann", "10.00", "Ann|Bob|Zed"])
        w.writerow(["2024-01-06T00:00:00+00:00", "X", "10.00", "X|Y"])
    hist = read_history(str(p))
    balances = {"Ann": money(Decimal("5")), "Bob": money(Decimal("5")), "Zed": money(Decimal("5"))}
    assert select_payer(balances, ["Ann", "Bob", "Zed"], tie_strategy="round_robin", history=hist) == "Bob"


def test_history_round_trip(tmp_path):
    """Appending and then reading a row yields identical values."""
    p = tmp_path / "h.csv"
    append_history_row(str(p), "2024-02-01T12:00:00+00:00", "Ann", Decimal("12.34"), ["Ann", "Bob"])
    hist = read_history(str(p))
    assert len(hist) == 1
    row = hist[0]
    assert row["payer"] == "Ann"
    assert abs(row["total_cost"] - 12.34) < 1e-9
    assert row["people"] == ["Ann", "Bob"]

"""
Fairness model:
  - Each round, EVERY included person is debited by their own price (consumption).
  - The payer is credited with the round TOTAL (they covered everyone).
  - Balances therefore equal:  total_paid - total_consumed
Next payer:
  - Lowest balance (owes most) wins, ties broken per `tie` strategy.

API:
  GET  /api/state
  GET  /api/next?people=A&people=B&...&tie=least_recent|alpha|random|round_robin
  POST /api/run   { people:[...], tie:"..." }          # Ledger update is always applied
  POST /api/set-price { name, price }                  # Validates name & positive price (Decimal)
  POST /api/remove-person { name }
  POST /api/reset-balances { clear_history: bool }     # Zero balances; optional history clear
  POST /api/clear-history                              # Clear history only (balances untouched)
  (Static) /
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
from decimal import Decimal

from storage import (
    PRICES_FILE, BALANCES_FILE, HISTORY_FILE,
    load_json, save_json, ensure_history, read_history, append_history_row,
    normalize_prices, normalize_balances, compute_total_cost,
    select_payer, now_iso, reset_history, money,
    validate_person_name, parse_price_to_decimal,
)

BASE_DIR = os.path.dirname(__file__)
FRONTEND_BUILD_DIR = os.path.join(BASE_DIR, "..", "frontend", "dist")

app = Flask(__name__, static_folder=FRONTEND_BUILD_DIR, static_url_path="/")
CORS(app, resources={r"/api/*": {"origins": "*"}})


def _ensure_defaults():
    """Load prices/balances (seed if empty) and ensure history exists."""
    raw_prices = load_json(PRICES_FILE, {})
    raw_balances = load_json(BALANCES_FILE, {})
    ensure_history(HISTORY_FILE)

    if not raw_prices:
        raw_prices = {"Bob": 4.50, "Jim": 3.00, "Sara": 5.00}

    prices_dec = normalize_prices(raw_prices)
    balances_dec = normalize_balances(raw_balances)

    for name in prices_dec.keys():
        balances_dec.setdefault(name, Decimal("0.00"))

    save_json(BALANCES_FILE, {k: float(v) for k, v in balances_dec.items()})
    save_json(PRICES_FILE, {k: float(v) for k, v in prices_dec.items()})
    return prices_dec, balances_dec


@app.get("/api/state")
def get_state():
    """Return current prices, balances, and history."""
    prices_dec, balances_dec = _ensure_defaults()
    return jsonify({
        "prices": {k: float(v) for k, v in prices_dec.items()},
        "balances": {k: float(v) for k, v in balances_dec.items()},
        "history": read_history(HISTORY_FILE),
    })


@app.get("/api/next")
def api_next():
    """
    Preview next payer (no mutation).
    Query: people=A&people=B&...&tie=least_recent|alpha|random|round_robin
    """
    prices_dec, balances_dec = _ensure_defaults()
    people = request.args.getlist("people") or list(prices_dec.keys())
    tie = (request.args.get("tie") or "least_recent").strip().lower()

    total_dec, included = compute_total_cost(prices_dec, people)
    if not included:
        return jsonify({"error": "No provided people match prices"}), 400

    payer = select_payer(balances_dec, included, tie_strategy=tie, history=read_history(HISTORY_FILE))
    return jsonify({"payer": payer, "total_cost": float(total_dec), "included": included, "tie": tie})


@app.post("/api/run")
def api_run():
    """
    Run a ledger round (mutates balances + history).
    Body: { "people": [...], "tie": "..." }
      - debit each included person by their price
      - credit payer with the round total
    """
    payload = request.get_json(silent=True) or {}
    people = payload.get("people") or []
    tie = (payload.get("tie") or "least_recent").strip().lower()

    prices_dec, balances_dec = _ensure_defaults()
    if not people:
        people = list(prices_dec.keys())

    total_dec, included = compute_total_cost(prices_dec, people)
    if not included:
        return jsonify({"error": "No provided people match prices"}), 400

    payer = select_payer(balances_dec, included, tie_strategy=tie, history=read_history(HISTORY_FILE))

    for p in included:
        balances_dec[p] = money(balances_dec.get(p, Decimal("0")) - prices_dec[p])
    balances_dec[payer] = money(balances_dec[payer] + total_dec)

    save_json(BALANCES_FILE, {k: float(v) for k, v in balances_dec.items()})
    ts = now_iso()
    append_history_row(HISTORY_FILE, ts, payer, total_dec, included)

    return jsonify({
        "timestamp": ts,
        "payer": payer,
        "total_cost": float(total_dec),
        "included": included,
        "tie": tie,
        "prices": {k: float(v) for k, v in prices_dec.items()},
        "balances": {k: float(v) for k, v in balances_dec.items()},
        "history": read_history(HISTORY_FILE),
    })


@app.post("/api/reset-balances")
def api_reset_balances():
    """
    Zero all balances; optionally clear history as well.
    Body: { "clear_history": bool }
    """
    payload = request.get_json(silent=True) or {}
    clear_history = bool(payload.get("clear_history"))

    prices_dec, _ = _ensure_defaults()
    zeroed = {k: 0.0 for k in prices_dec.keys()}
    save_json(BALANCES_FILE, zeroed)

    if clear_history:
        reset_history(HISTORY_FILE)

    return jsonify({
        "ok": True,
        "prices": {k: float(v) for k, v in prices_dec.items()},
        "balances": zeroed,
        "history": read_history(HISTORY_FILE),
    })


@app.post("/api/clear-history")
def api_clear_history():
    """
    Clear history ONLY (balances remain unchanged).
    """
    reset_history(HISTORY_FILE)
    return jsonify({"ok": True, "history": read_history(HISTORY_FILE)})


@app.post("/api/set-price")
def api_set_price():
    """
    Upsert a price with validation.
    Body: { "name": str (1–40 letters/spaces/-/'), "price": number|string > 0 }
    """
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    price_raw = payload.get("price")

    if not validate_person_name(name):
        return jsonify({"error": "Invalid name. Use 1–40 letters, spaces, - or ' only."}), 400

    price_dec = parse_price_to_decimal(price_raw)
    if price_dec is None or price_dec <= 0:
        return jsonify({"error": "Invalid price. Must be a positive number."}), 400

    prices = load_json(PRICES_FILE, {})
    balances = load_json(BALANCES_FILE, {})
    prices[name] = float(price_dec)
    balances.setdefault(name, 0.0)
    save_json(PRICES_FILE, prices)
    save_json(BALANCES_FILE, balances)

    return jsonify({"ok": True, "prices": prices, "balances": balances})


@app.post("/api/remove-person")
def api_remove_person():
    """
    Remove a person from prices/balances (history unchanged).
    Body: { "name": str }
    """
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400

    prices = load_json(PRICES_FILE, {})
    balances = load_json(BALANCES_FILE, {})
    removed = False
    if name in prices:
        del prices[name]; removed = True
    if name in balances:
        del balances[name]; removed = True

    save_json(PRICES_FILE, prices)
    save_json(BALANCES_FILE, balances)
    return jsonify({"ok": removed, "prices": prices, "balances": balances})


@app.get("/")
def serve_index():
    idx = os.path.join(FRONTEND_BUILD_DIR, "index.html")
    if os.path.exists(idx):
        return send_from_directory(FRONTEND_BUILD_DIR, "index.html")
    return "Frontend not built yet. Run `npm install && npm run build`.", 200


@app.get("/<path:path>")
def serve_static(path):
    full = os.path.join(FRONTEND_BUILD_DIR, path)
    if os.path.exists(full):
        return send_from_directory(FRONTEND_BUILD_DIR, path)
    if os.path.exists(os.path.join(FRONTEND_BUILD_DIR, "index.html")):
        return send_from_directory(FRONTEND_BUILD_DIR, "index.html")
    return "Not found", 404


if __name__ == "__main__":
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    if not os.path.exists(PRICES_FILE):
        save_json(PRICES_FILE, {"Bob": 4.5, "Jim": 3.0, "Sara": 5.0})
    if not os.path.exists(BALANCES_FILE):
        save_json(BALANCES_FILE, {"Bob": 0.0, "Jim": 0.0, "Sara": 0.0})
    ensure_history(HISTORY_FILE)
    app.run(host="0.0.0.0", port=5000, debug=True)

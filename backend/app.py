
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
from storage import (
    PRICES_FILE, BALANCES_FILE, HISTORY_FILE,
    load_json, save_json, ensure_history, compute_total_cost, select_payer,
    append_history_row, read_history, now_iso
)

FRONTEND_BUILD_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
app = Flask(__name__, static_folder=FRONTEND_BUILD_DIR, static_url_path="/")
CORS(app, resources={r"/api/*": {"origins": "*"}})

def _ensure_defaults():
    prices = load_json(PRICES_FILE, {})
    balances = load_json(BALANCES_FILE, {})
    ensure_history(HISTORY_FILE)
    return prices, balances

@app.get("/api/state")
def get_state():
    prices, balances = _ensure_defaults()
    history = read_history(HISTORY_FILE)
    return jsonify({"prices": prices, "balances": balances, "history": history})

@app.get("/api/next")
def api_next():
    prices, balances = _ensure_defaults()
    people = request.args.getlist("people")
    if not people:
        people = list(prices.keys())
    for p in people:
        balances.setdefault(p, 0.0)
    payer = select_payer(balances, people)
    total, included = compute_total_cost(prices, people)
    return jsonify({"payer": payer, "total_cost": total, "included": included})

@app.post("/api/run")
def api_run():
    payload = request.get_json(silent=True) or {}
    people = payload.get("people") or []
    prices, balances = _ensure_defaults()
    if not prices:
        return jsonify({"error": "No prices configured"}), 400
    if not people:
        people = list(prices.keys())
    total, included = compute_total_cost(prices, people)
    if not included:
        return jsonify({"error": "No provided people match prices"}), 400
    for p in included:
        balances.setdefault(p, 0.0)
    payer = select_payer(balances, included)
    balances[payer] = float(balances.get(payer, 0.0)) + float(total)
    save_json(BALANCES_FILE, balances)
    ts = now_iso()
    append_history_row(HISTORY_FILE, ts, payer, total, included)
    history = read_history(HISTORY_FILE)
    return jsonify({"timestamp": ts, "payer": payer, "total_cost": total, "included": included, "prices": prices, "balances": balances, "history": history})

@app.post("/api/set-price")
def api_set_price():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    price = payload.get("price")
    if not name or price is None:
        return jsonify({"error": "name and price required"}), 400
    try:
        price = float(price)
        if price <= 0:
            raise ValueError()
    except Exception:
        return jsonify({"error": "price must be a positive number"}), 400
    prices, balances = _ensure_defaults()
    prices[name] = price
    balances.setdefault(name, 0.0)
    save_json(PRICES_FILE, prices)
    save_json(BALANCES_FILE, balances)
    return jsonify({"ok": True, "prices": prices, "balances": balances})

@app.post("/api/remove-person")
def api_remove_person():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    prices, balances = _ensure_defaults()
    removed = False
    if name in prices:
        del prices[name]; removed = True
    if name in balances:
        del balances[name]; removed = True
    save_json(PRICES_FILE, prices)
    save_json(BALANCES_FILE, balances)
    return jsonify({"ok": removed, "prices": prices, "balances": balances})

@app.post("/api/reset-balances")
def api_reset_balances():
    prices, balances = _ensure_defaults()
    balances = {k: 0.0 for k in prices.keys()}
    save_json(BALANCES_FILE, balances)
    return jsonify({"ok": True, "balances": balances})

@app.get("/")
def serve_index():
    idx = os.path.join(FRONTEND_BUILD_DIR, "index.html")
    if os.path.exists(idx):
        return send_from_directory(FRONTEND_BUILD_DIR, "index.html")
    return "Frontend not built yet. Run `npm install && npm run build` in the frontend folder.", 200

@app.get("/<path:path>")
def serve_static(path):
    full = os.path.join(FRONTEND_BUILD_DIR, path)
    if os.path.exists(full):
        return send_from_directory(FRONTEND_BUILD_DIR, path)
    if os.path.exists(os.path.join(FRONTEND_BUILD_DIR, "index.html")):
        return send_from_directory(FRONTEND_BUILD_DIR, "index.html")
    return "Not found", 404

if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
    if not os.path.exists(PRICES_FILE):
        save_json(PRICES_FILE, {"Bob":4.5,"Jim":3.0,"Sara":5.0,"Tom":4.0,"Anna":4.75,"Mike":3.5,"Linda":4.25})
    if not os.path.exists(BALANCES_FILE):
        save_json(BALANCES_FILE, {"Bob":0.0,"Jim":0.0,"Sara":0.0,"Tom":0.0,"Anna":0.0,"Mike":0.0,"Linda":0.0})
    ensure_history(HISTORY_FILE)
    app.run(host="0.0.0.0", port=5000, debug=True)

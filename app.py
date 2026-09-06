from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json, os, threading
from datetime import datetime

app = Flask(__name__, static_folder=".")
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "submissions.json")
lock = threading.Lock()

# ── Helpers ──────────────────────────────────────────────
def read_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def write_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# IDs from index.html are strings like "TVT-1234567890"
# IDs added manually from admin are integers — handle both
def find_entry(data, raw_id):
    # try string match first
    entry = next((s for s in data if str(s["id"]) == str(raw_id)), None)
    return entry

def next_int_id(data):
    int_ids = [s["id"] for s in data if isinstance(s["id"], int)]
    return max(int_ids, default=0) + 1

# ── Static pages ─────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/admin")
def admin():
    return send_from_directory(".", "admin.html")

# ── API: submit from presale page (index.html) ───────────
@app.route("/api/submit", methods=["POST"])
def submit():
    body     = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip().lower()
    wallet   = (body.get("wallet")   or "").strip()
    usdt     = float(body.get("usdt") or body.get("robin") or 0)
    tvt      = float(body.get("tvt")  or 0)
    status   = (body.get("status") or "pending").strip()
    ext_id   = body.get("id")  # index.html sends "TVT-<timestamp>"

    if not username or not wallet:
        return jsonify({"ok": False, "error": "Missing fields"}), 400

    with lock:
        data     = read_data()
        existing = next((s for s in data if s["username"] == username), None)

        # Block duplicate username for non-connected submissions
        if existing and status not in ("connected",):
            return jsonify({"ok": False, "error": "Username already taken"}), 409

        entry = {
            "id":       ext_id if ext_id else next_int_id(data),
            "username": username,
            "wallet":   wallet,
            "usdt":     usdt,
            "tvt":      tvt,
            "status":   status,
            "date":     datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        }

        if existing and status == "connected":
            data[data.index(existing)] = {**existing, **entry}
        else:
            data.append(entry)

        write_data(data)

    return jsonify({"ok": True, "id": entry["id"]}), 201

# ── API: get all submissions (admin) ─────────────────────
@app.route("/api/submissions", methods=["GET"])
def get_submissions():
    return jsonify(read_data())

# ── API: update a submission (admin) ─────────────────────
@app.route("/api/submissions/<string:sub_id>", methods=["PATCH"])
def update_submission(sub_id):
    body = request.get_json(silent=True) or {}
    with lock:
        data  = read_data()
        entry = find_entry(data, sub_id)
        if not entry:
            return jsonify({"ok": False, "error": "Not found"}), 404

        if "tvt"    in body: entry["tvt"]    = float(body["tvt"])
        if "status" in body: entry["status"] = body["status"]
        if "usdt"   in body: entry["usdt"]   = float(body["usdt"])
        if "robin"  in body: entry["usdt"]   = float(body["robin"])
        write_data(data)

    return jsonify({"ok": True, "entry": entry})

# ── API: add entry manually (admin) ──────────────────────
@app.route("/api/submissions", methods=["POST"])
def add_submission():
    body     = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip().lower()
    wallet   = (body.get("wallet")   or "").strip()
    usdt     = float(body.get("usdt") or body.get("robin") or 0)
    tvt      = float(body.get("tvt")  or 0)
    status   = body.get("status", "pending")

    if not username or not wallet:
        return jsonify({"ok": False, "error": "Missing fields"}), 400

    with lock:
        data  = read_data()
        entry = {
            "id":       next_int_id(data),
            "username": username,
            "wallet":   wallet,
            "usdt":     usdt,
            "tvt":      tvt,
            "status":   status,
            "date":     datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        }
        data.append(entry)
        write_data(data)

    return jsonify({"ok": True, "entry": entry}), 201

if __name__ == "__main__":
    app.run(debug=True, port=5000)

"""
Flask app — serves cached ladder JSON to the frontend.
"""

import json
import subprocess
import sys
from pathlib import Path
from flask import Flask, jsonify, send_from_directory

DATA_DIR = Path(__file__).parent / "data"
STATIC_DIR = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR))


def load_ladder(filename: str) -> dict | None:
    path = DATA_DIR / filename
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/data/<path:filename>")
def serve_data(filename):
    return send_from_directory(DATA_DIR, filename)


@app.route("/banner.png")
def serve_banner():
    return send_from_directory(Path(__file__).parent, "banner.png")


@app.route("/api/leagues")
def leagues():
    from scraper import LEAGUES, slug
    # return leagues in the canonical order defined in scraper.py
    order = {slug(k): i for i, k in enumerate(LEAGUES)}
    files = list(DATA_DIR.glob("ladder_*.json"))
    result = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        lid = f.stem.removeprefix("ladder_")
        result.append({
            "id": lid,
            "name": data["league"],
            "count": data["count"],
            "fetched_at": data["fetched_at"],
            "_order": order.get(lid, 99),
        })
    result.sort(key=lambda x: x.pop("_order"))
    return jsonify(result)


@app.route("/api/ladder/<league_id>")
def ladder(league_id: str):
    data = load_ladder(f"ladder_{league_id}.json")
    if data is None:
        return jsonify({"error": "No data for this league. Run scraper.py first."}), 404
    return jsonify(data)


@app.route("/api/refresh/<league_id>", methods=["POST"])
def refresh(league_id: str):
    from scraper import LEAGUES, slug
    name_map = {slug(k): k for k in LEAGUES}
    league_name = name_map.get(league_id)
    if not league_name:
        return jsonify({"error": "Unknown league"}), 404
    subprocess.Popen([sys.executable, "scraper.py", league_name],
                     cwd=Path(__file__).parent)
    return jsonify({"status": "refresh started", "league": league_name})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

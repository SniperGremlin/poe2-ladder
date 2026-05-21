"""
Flask app — serves cached ladder JSON to the frontend.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

DATA_DIR = Path(__file__).parent / "data"
STATIC_DIR = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR))

VALID_LEAGUES = {"Standard", "Hardcore", "Solo Self-Found", "Hardcore SSF"}
VALID_ASCENDANCIES = {
    "Titan", "Warbringer", "Smith of Kitava",
    "Deadeye", "Pathfinder",
    "Infernalist", "Blood Mage",
    "Invoker", "Acolyte of Chayula", "Martial Artist",
    "Witchhunter", "Gemling Legionnaire", "Tactician",
    "Stormweaver", "Chronomancer", "Disciple of Varashta",
    "Shaman", "Oracle",
    "Amazon", "Ritualist", "Spirit Walker",
}


def load_ladder(filename: str) -> dict | None:
    path = DATA_DIR / filename
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/survey")
def survey():
    return send_from_directory(STATIC_DIR, "survey.html")


@app.route("/results")
def results_page():
    return send_from_directory(STATIC_DIR, "results.html")


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


@app.route("/api/survey", methods=["POST"])
def submit_survey():
    data = request.get_json(silent=True) or {}
    ascendancy = data.get("ascendancy", "").strip()
    league = data.get("league", "").strip()

    if ascendancy not in VALID_ASCENDANCIES or league not in VALID_LEAGUES:
        return jsonify({"error": "Invalid submission"}), 400

    survey_file = DATA_DIR / "survey_responses.json"
    responses = json.loads(survey_file.read_text(encoding="utf-8")) if survey_file.exists() else []
    responses.append({
        "ascendancy": ascendancy,
        "league": league,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    survey_file.write_text(json.dumps(responses, indent=2), encoding="utf-8")
    return jsonify({"status": "ok", "total": len(responses)})


@app.route("/api/survey/results")
def survey_results():
    survey_file = DATA_DIR / "survey_responses.json"
    if not survey_file.exists():
        return jsonify({"total": 0, "by_league": {}})

    responses = json.loads(survey_file.read_text(encoding="utf-8"))
    by_league = {}
    for r in responses:
        league = r["league"]
        asc = r["ascendancy"]
        if league not in by_league:
            by_league[league] = {}
        by_league[league][asc] = by_league[league].get(asc, 0) + 1

    return jsonify({"total": len(responses), "by_league": by_league})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

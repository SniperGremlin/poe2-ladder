"""
Scrapes the Path of Exile 2 ladder page and saves to JSON cache.
Run once daily — each run overwrites data/ladder_<league>.json
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Seasonal leagues first (current season: Runes of Aldur / Return of the Ancients 0.5.0), then permanent
LEAGUES = {
    "HC SSF Runes of Aldur": "https://pathofexile2.com/ladder/HC%20SSF%20Runes%20of%20Aldur",
    "HC Runes of Aldur":     "https://pathofexile2.com/ladder/HC%20Runes%20of%20Aldur",
    "SSF Runes of Aldur":    "https://pathofexile2.com/ladder/SSF%20Runes%20of%20Aldur",
    "Runes of Aldur":        "https://pathofexile2.com/ladder/Runes%20of%20Aldur",
    "Hardcore SSF":          "https://pathofexile2.com/ladder/Hardcore%20SSF",
    "Hardcore":              "https://pathofexile2.com/ladder/Hardcore",
    "Solo Self-Found":       "https://pathofexile2.com/ladder/Solo%20Self-Found",
    "Standard":              "https://pathofexile2.com/ladder/Standard",
}


def parse_character_cell(text: str) -> tuple[str, bool, bool]:
    dead = "(Dead)" in text
    retired = "(Retired)" in text
    name = text.replace("(Dead)", "").replace("(Retired)", "").strip()
    return name, dead, retired


def parse_experience(text: str) -> int:
    return int(text.replace(",", "").strip())


def scrape_league(league_name: str, url: str) -> list[dict]:
    print(f"  Scraping {league_name}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)

        rows = page.query_selector_all("tr")
        entries = []
        for row in rows[1:]:  # skip header
            cells = row.query_selector_all("td")
            if len(cells) < 6:
                continue
            rank = int(cells[0].inner_text().strip())
            account = cells[1].inner_text().strip()
            char_text = cells[2].inner_text().strip()
            char_name, dead, retired = parse_character_cell(char_text)
            cls = cells[3].inner_text().strip()
            level = int(cells[4].inner_text().strip())
            experience = parse_experience(cells[5].inner_text().strip())

            entries.append({
                "rank": rank,
                "account": account,
                "character": char_name,
                "class": cls,
                "level": level,
                "experience": experience,
                "dead": dead,
                "retired": retired,
            })

        browser.close()
    return entries


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def scrape_and_save(league_name: str, url: str):
    entries = scrape_league(league_name, url)
    out = {
        "league": league_name,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "entries": entries,
    }
    path = DATA_DIR / f"ladder_{slug(league_name)}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"  Saved {len(entries)} entries -> {path.name}")
    return league_name, len(entries)


def write_leagues_index():
    files = {slug(k): k for k in LEAGUES}
    result = []
    for lid, name in files.items():
        path = DATA_DIR / f"ladder_{lid}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        result.append({
            "id": lid,
            "name": name,
            "count": data["count"],
            "fetched_at": data["fetched_at"],
        })
    # preserve canonical order from LEAGUES dict
    order = {slug(k): i for i, k in enumerate(LEAGUES)}
    result.sort(key=lambda x: order.get(x["id"], 99))
    index_path = DATA_DIR / "leagues.json"
    index_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"  Wrote leagues index -> {index_path.name}")


def main(leagues_to_scrape: list[str] | None = None):
    targets = {k: v for k, v in LEAGUES.items()
               if leagues_to_scrape is None or k in leagues_to_scrape}

    print(f"Scraping {len(targets)} league(s) in parallel...")
    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        futures = {pool.submit(scrape_and_save, k, v): k for k, v in targets.items()}
        for fut in as_completed(futures):
            try:
                name, count = fut.result()
            except Exception as e:
                print(f"  ERROR scraping {futures[fut]}: {e}")

    write_leagues_index()


if __name__ == "__main__":
    args = sys.argv[1:] or None
    main(args)

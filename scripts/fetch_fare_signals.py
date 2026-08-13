"""
Pulls route/fare signals for candidate destinations from each tracked airport.

This is your proxy for "leakage" — you don't have Skyscanner's actual search
click data (that's proprietary and sold, per their Travel Insight Vision
product), but a flight-data API can tell you:
  - which routes currently have NO direct scheduled service (a genuine gap)
  - typical fares/routing time via the nearest connecting option
  - whether nearby competing airports (Heathrow, Manchester, Edinburgh) DO
    serve that destination directly (a proxy for demand existing regionally)

Pick ONE provider and fill in the API call. Two reasonable free-tier options:

  - AviationStack (aviationstack.com) — simple REST API, free tier ~100
    requests/month, good for route/schedule lookups.
  - Amadeus for Developers (developers.amadeus.com) — free "Self-Service"
    tier with generous limits, includes flight search + route data, more
    setup but richer data.

Usage:
    python fetch_fare_signals.py --config airports.yaml --out ../data/fare_signals.json
"""
import argparse
import json
import os
from pathlib import Path

import requests
import yaml

API_KEY = os.environ.get("FLIGHT_DATA_API_KEY")


def check_route_exists(origin: str, destination: str) -> dict:
    """
    Replace this with a real call to your chosen provider.
    Returns something like:
      {"origin": "NCL", "destination": "IST", "direct_route_exists": False,
       "nearest_connecting_options": [...], "typical_fare_gbp": None}

    Stub below shows the shape without making a real network call — wire up
    your provider's actual endpoint here.
    """
    if not API_KEY:
        raise RuntimeError(
            "Set FLIGHT_DATA_API_KEY env var (GitHub Actions secret) before running."
        )

    # Example shape for AviationStack-style route lookup — replace URL/params
    # with your provider's actual route-search endpoint.
    # resp = requests.get(
    #     "https://api.aviationstack.com/v1/routes",
    #     params={"access_key": API_KEY, "dep_iata": origin, "arr_iata": destination},
    #     timeout=15,
    # )
    # resp.raise_for_status()
    # data = resp.json()
    # direct_exists = len(data.get("data", [])) > 0

    # Placeholder until wired up:
    direct_exists = None

    return {
        "origin": origin,
        "destination": destination,
        "direct_route_exists": direct_exists,
    }


def run(config_path: Path, out_path: Path) -> None:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    airports = [a["code"] for a in cfg["airports"]]
    destinations = cfg["candidate_destinations"]

    results = []
    for origin in airports:
        for dest in destinations:
            results.append(check_route_exists(origin, dest))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {len(results)} route checks to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("airports.yaml"))
    parser.add_argument("--out", type=Path, default=Path("../data/fare_signals.json"))
    args = parser.parse_args()
    run(args.config, args.out)

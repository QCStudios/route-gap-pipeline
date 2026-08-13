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


AVIATIONSTACK_BASE_URL = "http://api.aviationstack.com/v1"
# NOTE: AviationStack's free plan only allows plain HTTP, not HTTPS — using
# https:// here will fail on the free tier with a 401. Switch to https once
# you upgrade off the free plan.
#
# NOTE 2: AviationStack's own FAQ says airline route data ("routes" endpoint)
# requires a commercial/paid subscription, not just the free plan. Confirm
# this against your actual account once signed in — if the free tier really
# doesn't include /routes, the /flights endpoint (filtered by dep_iata +
# arr_iata + a specific flight_date) is the free-tier workaround: an empty
# result set for a route over several sampled dates is a reasonable (if
# noisier) proxy for "no direct service."


def check_route_exists(origin: str, destination: str) -> dict:
    """
    Calls AviationStack's routes endpoint to check whether a direct route
    exists between origin and destination. Returns:
      {"origin": "NCL", "destination": "IST", "direct_route_exists": bool|None}

    direct_route_exists is None if the API call itself failed (e.g. free
    tier lacks access to /routes) rather than a confirmed "no route" —
    keep this distinction, don't silently treat a failed call as a gap.
    """
    if not API_KEY:
        raise RuntimeError(
            "Set FLIGHT_DATA_API_KEY env var (GitHub Actions secret) before running."
        )

    resp = requests.get(
        f"{AVIATIONSTACK_BASE_URL}/routes",
        params={"access_key": API_KEY, "dep_iata": origin, "arr_iata": destination},
        timeout=15,
    )

    if resp.status_code != 200:
        print(
            f"WARN: routes lookup failed for {origin}->{destination} "
            f"(status {resp.status_code}: {resp.text[:200]}). "
            "If this is a 401/403, your plan likely doesn't include /routes — "
            "see notes above about the /flights fallback."
        )
        return {"origin": origin, "destination": destination, "direct_route_exists": None}

    data = resp.json()
    direct_exists = len(data.get("data", [])) > 0

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

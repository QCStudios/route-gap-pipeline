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
# https:// here will fail on the free tier with a 401.
#
# NOTE 2: CONFIRMED — the /routes endpoint returns
# {"error":{"code":"function_access_restricted", ...}} on the free plan.
# It is paid-only. This script therefore uses /flights instead, which the
# free tier does support, as a proxy for "is this route served."
#
# How the /flights proxy works: we query for scheduled flights on a given
# origin/destination pair across a handful of sample dates. If none are
# found on any sampled date, treat it as evidence (not proof) of no direct
# service. This is noisier than a proper routes lookup — a low-frequency
# route (e.g. 2x/week) could show as "no route" on a day it doesn't fly.
# Sample multiple dates (a full week) to reduce that risk. Free tier is
# 100 requests/month, so budget carefully: 6 airports x 10 destinations x
# 7 sample days = 420 calls, well over budget. Trim either the airport
# list, destination list, or sample-day count in airports.yaml/here to fit.

SAMPLE_DATES_TO_CHECK = 3  # calls used per route pair; keep low on free tier


def check_route_exists(origin: str, destination: str, sample_dates: list[str]) -> dict:
    """
    Queries AviationStack's /flights endpoint for scheduled flights on the
    origin->destination pair, on each date in sample_dates. Returns:
      {"origin": ..., "destination": ..., "direct_route_exists": bool|None,
       "dates_checked": [...], "flights_found": int}

    direct_route_exists is None only if every API call failed outright
    (e.g. bad key, rate limit) — a clean "zero flights found across all
    sampled dates" is recorded as False (likely no direct route), not None,
    since /flights access is confirmed working on the free plan.
    """
    if not API_KEY:
        raise RuntimeError(
            "Set FLIGHT_DATA_API_KEY env var (GitHub Actions secret) before running."
        )

    flights_found = 0
    successful_calls = 0

    for flight_date in sample_dates:
        resp = requests.get(
            f"{AVIATIONSTACK_BASE_URL}/flights",
            params={
                "access_key": API_KEY,
                "dep_iata": origin,
                "arr_iata": destination,
                "flight_date": flight_date,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            print(
                f"WARN: flights lookup failed for {origin}->{destination} "
                f"on {flight_date} (status {resp.status_code}: {resp.text[:200]})."
            )
            continue

        successful_calls += 1
        data = resp.json()
        flights_found += len(data.get("data", []))

    if successful_calls == 0:
        # every call failed — genuinely unknown, not evidence of anything
        return {
            "origin": origin,
            "destination": destination,
            "direct_route_exists": None,
            "dates_checked": sample_dates,
            "flights_found": 0,
        }

    return {
        "origin": origin,
        "destination": destination,
        "direct_route_exists": flights_found > 0,
        "dates_checked": sample_dates,
        "flights_found": flights_found,
    }


import datetime

# Free tier = 100 requests/month. Running weekly (4x/month) means ~25
# requests per run is the safe budget, leaving headroom for retries/errors.
MAX_REQUESTS_PER_RUN = 20


def sample_dates_for_next_week() -> list[str]:
    """Returns a few near-future dates to sample flights for."""
    today = datetime.date.today()
    return [(today + datetime.timedelta(days=d)).isoformat() for d in (2, 4, 6)]


def run(config_path: Path, out_path: Path, state_path: Path) -> None:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    airports = [a["code"] for a in cfg["airports"]]
    destinations = cfg["candidate_destinations"]
    all_pairs = [(o, d) for o in airports for d in destinations]

    sample_dates = sample_dates_for_next_week()
    pairs_per_run = max(1, MAX_REQUESTS_PER_RUN // len(sample_dates))

    # Rotate through all_pairs across runs so the whole matrix gets covered
    # over several weeks instead of blowing the monthly quota in one run.
    state = {"offset": 0}
    if state_path.exists():
        state = json.loads(state_path.read_text())

    offset = state.get("offset", 0) % len(all_pairs)
    this_run_pairs = (all_pairs * 2)[offset : offset + pairs_per_run]  # wrap around

    results = []
    for origin, dest in this_run_pairs:
        results.append(check_route_exists(origin, dest, sample_dates))

    # Merge with any previously-saved results for pairs not checked this run,
    # so gaps.json always has the full picture, just with staler data for
    # pairs not yet re-checked this cycle.
    existing = []
    if out_path.exists():
        existing = json.loads(out_path.read_text())
    existing_by_pair = {(r["origin"], r["destination"]): r for r in existing}
    for r in results:
        existing_by_pair[(r["origin"], r["destination"])] = r
    merged = list(existing_by_pair.values())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, indent=2))

    new_offset = (offset + pairs_per_run) % len(all_pairs)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"offset": new_offset}))

    print(
        f"Checked {len(this_run_pairs)} pairs this run "
        f"(offset {offset} -> {new_offset} of {len(all_pairs)} total pairs). "
        f"Wrote {len(merged)} total results to {out_path}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("airports.yaml"))
    parser.add_argument("--out", type=Path, default=Path("../data/fare_signals.json"))
    parser.add_argument("--state", type=Path, default=Path("../data/rotation_state.json"))
    args = parser.parse_args()
    run(args.config, args.out, args.state)

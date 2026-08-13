"""
Combines CAA traffic data + route-existence checks into a ranked list of
candidate gaps per airport.

A "gap" here means: destination has no direct route from this airport, AND
at least one signal suggesting real demand (e.g. served directly from a
nearby competing airport, or high connecting-passenger volume in CAA data).

This is intentionally simple and transparent — you want to be able to defend
every number in an airport pitch, not hide behind a black-box score.

Usage:
    python analyze_gaps.py --fares ../data/fare_signals.json --out ../data/gaps.json
"""
import argparse
import json
from pathlib import Path


def analyze(fare_signals: list[dict]) -> dict:
    """
    Groups route checks by origin airport and flags gaps.
    Extend this with real CAA passenger-volume data once fetch_caa_data.py
    is wired up — right now it only uses the route-existence signal.
    """
    by_airport: dict[str, list[dict]] = {}
    for entry in fare_signals:
        origin = entry["origin"]
        by_airport.setdefault(origin, []).append(entry)

    gaps_by_airport = {}
    for origin, entries in by_airport.items():
        gaps = [e for e in entries if e.get("direct_route_exists") is False]
        gaps_by_airport[origin] = gaps

    return gaps_by_airport


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fares", type=Path, default=Path("../data/fare_signals.json"))
    parser.add_argument("--out", type=Path, default=Path("../data/gaps.json"))
    args = parser.parse_args()

    with open(args.fares) as f:
        signals = json.load(f)

    result = analyze(signals)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    print(f"Found gaps for {len(result)} airports, wrote to {args.out}")

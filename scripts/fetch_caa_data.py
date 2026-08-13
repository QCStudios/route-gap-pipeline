"""
Downloads UK CAA's published airport/route statistics.

The CAA publishes monthly and annual airport data (passenger numbers, route
traffic) as CSV/XLSX at:
  https://www.caa.co.uk/data-and-analysis/uk-aviation-market/airports/uk-airport-data/

This script does NOT scrape unpublished data — everything here is public,
free, and intended by the CAA for exactly this kind of analysis. Check the
current page structure before relying on this in production; the CAA
occasionally reorganises its data pages, so the URL patterns below may need
updating.

Usage:
    python fetch_caa_data.py --out ../data/caa_latest.csv
"""
import argparse
import sys
from pathlib import Path

import requests
import yaml

CAA_INDEX_URL = "https://www.caa.co.uk/data-and-analysis/uk-aviation-market/airports/uk-airport-data/"


def load_airport_list(config_path: Path) -> list[str]:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    return [a["code"] for a in cfg["airports"]]


def fetch_caa_dataset(out_path: Path) -> None:
    """
    Fetches the latest published CAA airport data file.

    NOTE: The CAA site structure changes periodically and the exact download
    link for "latest month" needs to be located manually the first time you
    set this up (open the index URL above, find the current month's CSV/XLSX
    link, and hardcode it here or add simple link-scraping logic).
    This stub fetches a placeholder — replace CAA_DATA_URL with the real
    current link before first run.
    """
    CAA_DATA_URL = "REPLACE_WITH_CURRENT_CAA_CSV_URL"  # noqa: N806

    if CAA_DATA_URL.startswith("REPLACE"):
        print(
            "Set CAA_DATA_URL in fetch_caa_data.py to the current month's "
            f"CAA data file, found at {CAA_INDEX_URL}",
            file=sys.stderr,
        )
        sys.exit(1)

    resp = requests.get(CAA_DATA_URL, timeout=30)
    resp.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(resp.content)
    print(f"Saved CAA data to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("../data/caa_latest.csv"))
    parser.add_argument(
        "--config", type=Path, default=Path("airports.yaml")
    )
    args = parser.parse_args()

    airports = load_airport_list(args.config)
    print(f"Tracking {len(airports)} airports: {', '.join(airports)}")
    fetch_caa_dataset(args.out)

"""
Turns the structured gap data into a readable, evidence-grounded report per
airport using the Claude API. This is the "AI-integrated" step — it doesn't
invent numbers, it writes up the numbers you already computed.

Usage:
    python generate_report.py --gaps ../data/gaps.json --out-dir ../reports
"""
import argparse
import json
import os
from datetime import date
from pathlib import Path

import anthropic

REPORT_PROMPT = """You are drafting a short, evidence-based route-opportunity \
memo for an airport route-development team. You will be given structured \
data about candidate destination gaps for one airport. Write a concise memo \
(under 400 words) that:

- States clearly which destinations currently have no direct route from \
this airport, based only on the data given.
- Does NOT invent passenger numbers, fares, or demand figures that are not \
present in the data.
- Where the data is incomplete (e.g. route-existence unknown), say so \
explicitly rather than guessing.
- Ends with a short "what evidence would strengthen this case" section \
listing what data to gather next (e.g. CAA passenger volumes, leakage via \
competing airports).

Airport: {airport}
Data: {data}
"""


def generate_report(client: anthropic.Anthropic, airport: str, data: list[dict]) -> str:
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": REPORT_PROMPT.format(
                    airport=airport, data=json.dumps(data, indent=2)
                ),
            }
        ],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def run(gaps_path: Path, out_dir: Path) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Set ANTHROPIC_API_KEY (GitHub Actions secret).")

    client = anthropic.Anthropic(api_key=api_key)

    with open(gaps_path) as f:
        gaps_by_airport = json.load(f)

    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    for airport, data in gaps_by_airport.items():
        report_text = generate_report(client, airport, data)
        out_path = out_dir / f"{airport}_{today}.md"
        out_path.write_text(f"# Route Gap Report: {airport} ({today})\n\n{report_text}\n")
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gaps", type=Path, default=Path("../data/gaps.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("../reports"))
    args = parser.parse_args()
    run(args.gaps, args.out_dir)

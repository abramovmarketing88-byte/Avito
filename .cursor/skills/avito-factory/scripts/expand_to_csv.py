#!/usr/bin/env python3
"""Expand spintax templates into Avito bulk-upload CSV.

Usage:
  python expand_to_csv.py --titles titles.txt --bodies bodies.txt --cities cities.txt --output out.csv
  python expand_to_csv.py --titles titles.txt --bodies bodies.txt --cities "Казань,Москва" --count 200 --output out.csv

titles.txt / bodies.txt: one spintax template per line (or one multi-line template per file section separated by ---)
cities.txt: one city per line
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from itertools import cycle
from pathlib import Path

CSV_HEADER_ROWS = [
    ["", "", ""],
    ["Title", "Description", "Address"],
    ["Обязательный", "Обязательный", "Обязательный"],
    ["Подробнее о параметре", "Подробнее о параметре", "Подробнее о параметре"],
]


def expand_spintax(text: str, rng: random.Random) -> str:
    """Recursively expand {a|b|c} spintax."""
    pattern = re.compile(r"\{([^{}]+)\}")

    def _replace(match: re.Match[str]) -> str:
        options = match.group(1).split("|")
        return rng.choice(options)

    prev = None
    current = text
    while prev != current:
        prev = current
        current = pattern.sub(_replace, current)
    return current


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    content = path.read_text(encoding="utf-8-sig").strip()
    if not content:
        return []
    if "\n---\n" in content:
        return [block.strip() for block in content.split("\n---\n") if block.strip()]
    return [line.strip() for line in content.splitlines() if line.strip()]


def parse_cities(value: str | None, cities_file: Path | None) -> list[str]:
    if cities_file:
        return load_lines(cities_file)
    if value:
        return [c.strip() for c in value.split(",") if c.strip()]
    return ["Россия"]


def generate_rows(
    title_templates: list[str],
    body_templates: list[str],
    cities: list[str],
    count: int,
    seed: int | None,
) -> list[tuple[str, str, str]]:
    if not title_templates or not body_templates:
        raise ValueError("Need at least one title and one body template")

    rng = random.Random(seed)
    rows: list[tuple[str, str, str]] = []
    city_cycle = cycle(cities)

    attempts = 0
    max_attempts = count * 20
    seen: set[tuple[str, str, str]] = set()

    while len(rows) < count and attempts < max_attempts:
        attempts += 1
        title_tpl = rng.choice(title_templates)
        body_tpl = rng.choice(body_templates)
        city = next(city_cycle)

        title = expand_spintax(title_tpl, rng).strip()
        body = expand_spintax(body_tpl, rng).strip()
        row = (title, body, city)

        if row in seen:
            continue
        seen.add(row)
        rows.append(row)

    return rows


def write_csv(path: Path, rows: list[tuple[str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        for header_row in CSV_HEADER_ROWS:
            writer.writerow(header_row)
        for title, description, address in rows:
            writer.writerow([title, description, address])


def main() -> int:
    parser = argparse.ArgumentParser(description="Expand spintax to Avito CSV")
    parser.add_argument("--titles", type=Path, required=True, help="File with title spintax templates")
    parser.add_argument("--bodies", type=Path, required=True, help="File with body spintax templates")
    parser.add_argument("--cities", type=str, help="Comma-separated cities")
    parser.add_argument("--cities-file", type=Path, help="File with one city per line")
    parser.add_argument("--count", type=int, default=50, help="Number of ad rows to generate")
    parser.add_argument("--output", type=Path, required=True, help="Output CSV path")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    args = parser.parse_args()

    title_templates = load_lines(args.titles)
    body_templates = load_lines(args.bodies)
    cities = parse_cities(args.cities, args.cities_file)

    rows = generate_rows(title_templates, body_templates, cities, args.count, args.seed)
    write_csv(args.output, rows)

    print(f"Wrote {len(rows)} rows to {args.output}")
    if len(rows) < args.count:
        print(f"Warning: requested {args.count}, got {len(rows)} unique rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

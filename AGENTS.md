# Avito

This repository ships the **`avito-factory` Cursor skill** (`.cursor/skills/avito-factory/`), a pipeline for mass-generating Avito classified ads and exporting them to a bulk-upload CSV (`Title`, `Description`, `Address`). See `.cursor/skills/avito-factory/SKILL.md` for the full workflow.

## Cursor Cloud specific instructions

### What this codebase is

There is no server or web app. The runnable "application" is two Python CLI scripts under `.cursor/skills/avito-factory/scripts/`:

- `generate_tatarstan_200.py` — builds the fixed Tatarstan 200-ad preset (50 Kazan / 20 Naberezhnye Chelny / 130 other RT cities) from a chat export.
- `expand_to_csv.py` — expands `{a|b|c}` spintax title/body templates against a city list into a bulk-upload CSV.

### Environment / dependencies

- Requires only Python 3 (standard library: `argparse`, `csv`, `random`, `re`, `json`, `pathlib`, `itertools`). There are **no** third-party packages, no lockfile, and no `requirements.txt`/`pyproject.toml`, so there is nothing to `pip install`.
- There is no configured linter or test framework. Use `python3 -m py_compile scripts/*.py` for a quick syntax check.

### Running the scripts (run from `.cursor/skills/avito-factory/`)

- Tatarstan 200 preset: `python3 scripts/generate_tatarstan_200.py --export data/avito-chat-export.txt --output output/avito-ads-tatarstan-200.csv`. Expect `200` rows and a 50/20/130 city split.
- Spintax expansion: `python3 scripts/expand_to_csv.py --titles <titles.txt> --bodies <bodies.txt> --cities-file <cities.txt> --count N --output output/out.csv --seed 42`.

### Gotchas

- The generated CSV always has a **4-row header** (blank row, `Title,Description,Address`, `Обязательный` row, `Подробнее о параметре` row) before the data rows, so a file with N ads has N+4 lines. This is the Avito bulk-upload format, not a bug.
- The `output/` directory is git-ignored (see `.cursor/skills/avito-factory/.gitignore`); generated CSVs are not committed.
- In `expand_to_csv.py`, spintax only expands `{opt1|opt2|...}`. A single-option token like `{city}` is **not** a substitution — it just yields the literal `city`. City values come from the separate `--cities`/`--cities-file` argument and populate the `Address` column.
- Files are read as `utf-8`/`utf-8-sig` and written as `utf-8`; content is Russian, so keep the terminal/editor UTF-8.

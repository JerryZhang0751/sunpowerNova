#!/usr/bin/env python3
"""
Generate a pre-filled weekly measurement CSV from prompts.csv.

For each prompt x model, emits one row with the keys filled in and the
measurement columns left blank. The operator then fills them in while running
the prompts in each target model.

Usage:
  python3 generate_week.py 1          # writes week-01.csv (full: 215 rows, W1/W4/W8)
  python3 generate_week.py 2          # writes week-02.csv (core: 75 rows, other weeks)

Full weeks (W1/W4/W8) emit all 43 prompts x 5 models = 215 rows; other weeks
emit only the core 15 prompts x 5 models = 75 rows (see FULL_WEEKS / CORE_IDS).
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).parent
# (model family, default version) — China-accessible set. Claude / Perplexity /
# Google AI Overviews dropped (not reachable in-region); DeepSeek + Qwen added.
# Operator may overwrite model_version in the CSV if a newer build is used.
MODELS = [
    ("ChatGPT", "gpt-5.5"),
    ("Gemini", "gemini-3.5-flash"),
    ("DeepSeek", "deepseek-v4-pro"),
    ("Grok", "grok-4.3"),
    ("Qwen", "qwen3.7-plus"),
]
RUNS = 1  # bump to 2 or 3 to repeat each prompt x model for stochasticity

# Measurement mix (cadence set 2026-07-19): full 215 rows on baseline/mid/final
# weeks, core 75 rows (15 prompts x 5 models) on the other weeks to keep the
# weekend operator load sustainable. Core 15 = representative prompts covering
# all 7 categories (C/S/D/K/M/B/G).
FULL_WEEKS = {1, 4, 8}  # W1 baseline / W4 mid / W8 final
CORE_IDS = {
    "C01", "C04",
    "S01", "S02",
    "D01", "D04",
    "K01", "K03",
    "M01", "M03",
    "B01", "B02",
    "G01", "G02", "G05",
}

HEADER = [
    "date", "week", "prompt_id", "model", "model_version", "run",
    "mentioned", "cited_with_link", "citation_position", "sentiment",
    "competitors_mentioned", "raw_answer_link", "notes",
]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: generate_week.py <week_number>", file=sys.stderr)
        return 2
    week = int(sys.argv[1])
    all_prompts = []
    with (HERE / "prompts.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            all_prompts.append(row["id"])
    is_full = week in FULL_WEEKS
    prompts = all_prompts if is_full else [p for p in all_prompts if p in CORE_IDS]
    scope = "full" if is_full else "core"

    out_name = f"week-{week:02d}.csv"
    out_path = HERE / out_name
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for pid in prompts:
            for model, version in MODELS:
                for run in range(1, RUNS + 1):
                    w.writerow([
                        "", f"W{week}", pid, model, version, run,
                        "", "", "", "", "", "", "",
                    ])
    print(f"wrote {out_path} [{scope}] — {len(prompts)} prompts x {len(MODELS)} models "
          f"x {RUNS} run(s) = {len(prompts)*len(MODELS)*RUNS} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

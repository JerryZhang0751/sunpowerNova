#!/usr/bin/env python3
"""
Fill one (prompt_id × model) row in week-XX.csv from parsed answer values.

Workflow: the operator runs a prompt in a model and saves the answer to
`answers/w{N}-{Model}-{PromptID}.md`. The assistant reads that file, judges the
fields, and calls this script to write them into the matching CSV row. This
keeps the parsing auditable (the exact command is the record) and avoids fragile
hand-editing of the CSV.

Updates the run=1 row for (prompt_id, model) in place. Refuses to overwrite an
already-filled row unless --force.

Usage:
  python3 fill_row.py 1 C01 Qwen \\
      --mentioned N --cited N \\
      --competitors "Canadian Solar;Tesla;Enphase" \\
      --link answers/w1-Qwen-C01.md \\
      --notes "联网生效；SunHestia 未出现" \\
      [--pos 1] [--sent neu] [--date 2026-07-19] [--force]
"""
import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("week", help="week number, e.g. 1")
    ap.add_argument("prompt_id", help="e.g. C01")
    ap.add_argument("model", help="ChatGPT | Gemini | DeepSeek | Grok | Qwen")
    ap.add_argument("--mentioned", help="Y or N")
    ap.add_argument("--cited", help="Y or N (cited_with_link)")
    ap.add_argument("--pos", help="citation position (int) — only if cited")
    ap.add_argument("--sent", help="pos | neu | neg — only if mentioned")
    ap.add_argument("--competitors", default=None,
                    help="semicolon list of brands (omit to leave unchanged; "
                         "pass \"\" to clear)")
    ap.add_argument("--link", default=None,
                    help="path/url to saved answer (omit to leave unchanged)")
    ap.add_argument("--notes", default=None,
                    help="free-text anomalies (omit to leave unchanged)")
    ap.add_argument("--date", help="YYYY-MM-DD run date")
    ap.add_argument("--force", action="store_true", help="overwrite a filled row")
    args = ap.parse_args()

    path = HERE / f"week-{int(args.week):02d}.csv"
    if not path.exists():
        print(f"!! {path} not found", file=sys.stderr)
        return 1

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    matched = 0
    for r in rows:
        if (r["prompt_id"] == args.prompt_id
                and r["model"] == args.model
                and str(r.get("run", "")) == "1"):
            if r.get("mentioned", "").strip() and not args.force:
                print(f"!! row already filled (use --force): "
                      f"{args.prompt_id}/{args.model}", file=sys.stderr)
                return 1
            if args.date is not None:
                r["date"] = args.date
            if args.mentioned is not None:
                r["mentioned"] = args.mentioned
            if args.cited is not None:
                r["cited_with_link"] = args.cited
            if args.pos is not None:
                r["citation_position"] = args.pos
            if args.sent is not None:
                r["sentiment"] = args.sent
            if args.competitors is not None:
                r["competitors_mentioned"] = args.competitors
            if args.link is not None:
                r["raw_answer_link"] = args.link
            if args.notes is not None:
                r["notes"] = args.notes
            matched += 1

    if matched == 0:
        print(f"!! no run=1 row for {args.prompt_id}/{args.model} in {path.name}",
              file=sys.stderr)
        return 1

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"updated {matched} row(s) in {path.name}: {args.prompt_id}/{args.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

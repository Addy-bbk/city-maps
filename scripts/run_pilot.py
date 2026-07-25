"""
Extract all cities from the pilot city list and output a summary of their extraction process:
Usage (from the project root, within the citymaps environment):
python scripts/run_pilot.py
"""

import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from citymaps import config, pipeline, validate
from citymaps.formats import read_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")


def main() -> int:
    rows = list(csv.DictReader(config.CITY_LIST.open()))
    records = []
    failures = []

    for row in rows:
        name = row["name"]
        query = row["query"]
        try:
            rec = pipeline.process_city(name, query)
            # Run the extraction pipeline on the city and store result
            # Extract the graph from the file created by the pipeline and pass it through validation
            # The goal here is to test whether the pipeline can write an acceptable file. 
            # It's not testing the pipeline or the validation. 
            G = read_graph(config.PROJECT_ROOT / rec["file"])
            rec.update(validate.validate(G))
            records.append(rec)
            print(
                f"  {name:<16} {rec['final_nodes']:>7,} nodes  "
                f"{rec['final_edges']:>7,} edges  "
                f"mean deg {rec['mean_degree']:.2f}  "
                f"planar={rec['is_planar']}  "
                f"checks={'PASS' if rec['passed'] else 'FAIL'}"
            )
        except Exception as exc:
            failures.append((name, repr(exc)))
            print(f"  {name:<16} FAILED: {exc}")

    if records:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        out = config.LOG_DIR / "pilot_results.csv"
        keys = sorted({k for r in records for k in r})
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(records)
        print(f"\nWrote {out}")

    print(f"\n{len(records)} succeeded, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

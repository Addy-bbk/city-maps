"""Execute the fixed-radius extraction on the city list.

Mirrors run_all.py — the same behaviour regarding politeness and provenance — however, 
it calls the fixed-radius pipeline and stores its results in its own results file; therefore the boundary-based dataset remains unaffected.

Usage (with project root and using the citymaps environment): 

python scripts/run_radius.py # Extract all cities, continue where last execution ended
python scripts/run_radius.py --restart # Ignore last executions results
python scripts/run_radius.py --limit 3 # Only extract up to 3 cities
python scripts/run_radius.py --radius 3000 # Use a different half-width

"""

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import osmnx as ox

from citymaps import config, pipeline_radius, validate
from citymaps.formats import read_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("run_radius")

REQUEST_TIMEOUT_S = 300
PAUSE_BETWEEN_CITIES_S = 5

RESULTS = config.LOG_DIR / "results_radius.csv"
FAILURES = config.LOG_DIR / "failures_radius.csv"

RESULT_FIELDS = [
    "city", "query", "region", "morphology",
    "centre_lat", "centre_lon", "radius_m", "crs",
    "raw_nodes", "final_nodes", "final_edges", "reduction_pct",
    "n_nodes", "n_edges", "mean_degree", "edge_node_ratio",
    "connected", "n_components", "n_self_loops", "n_isolated",
    "within_planar_bound", "plausible_mean_degree", "passed",
    "is_planar", "witness_computed", "kuratowski_size", "file",
]


def load_done() -> set:
    """Set of names that were previously marked successful. Which allows to resume an interrupted run without wasting time processing those again. """
    if not RESULTS.exists():
        return set()
    with RESULTS.open() as fh:
        return {row["city"] for row in csv.DictReader(fh)}


def append_row(path: Path, fields: list, row: dict) -> None:
    """Append one row to the file. If the file is new then the column headers are written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--restart", action="store_true",
                    help="delete prior results and start from scratch")
    ap.add_argument("--limit", type=int, default=None,
                    help="process at most this many new cities")
    ap.add_argument("--radius", type=int, default=pipeline_radius.RADIUS_M,
                    help="half-width of the extracted square, in metres")
    ap.add_argument("--list", type=Path, default=config.CITY_LIST,
                    help="path to the city CSV (default: configured list)")
    args = ap.parse_args()

    ox.settings.requests_timeout = REQUEST_TIMEOUT_S

    if args.restart:
        for p in (RESULTS, FAILURES):
            p.unlink(missing_ok=True)
        log.info("restart: cleared previous radius results")

    cities = list(csv.DictReader(args.list.open()))
    done = load_done()
    todo = [c for c in cities if c["name"] not in done]
    if args.limit:
        todo = todo[: args.limit]

    log.info("radius %d m | %d cities total, %d already done, %d to attempt",
             args.radius, len(cities), len(done), len(todo))

    succeeded = failed = 0
    for i, city in enumerate(todo, 1):
        name, query = city["name"], city["query"]
        log.info("[%d/%d] %s", i, len(todo), name)
        try:
            rec = pipeline_radius.process_city_radius(name, query, args.radius)
            G = read_graph(config.PROJECT_ROOT / rec["file"])
            rec.update(validate.validate(G))
            rec["region"] = city.get("region", "")
            rec["morphology"] = city.get("morphology", "")
            append_row(RESULTS, RESULT_FIELDS, rec)
            succeeded += 1
            log.info("      ok: %d nodes, %d edges, planar=%s, checks=%s",
                     rec["final_nodes"], rec["final_edges"],
                     rec["is_planar"], "PASS" if rec["passed"] else "FAIL")
        except Exception as exc:
            failed += 1
            append_row(FAILURES, ["city", "query", "error"],
                       {"city": name, "query": query, "error": repr(exc)})
            log.warning("      FAILED: %s", exc)

        if i < len(todo):
            time.sleep(PAUSE_BETWEEN_CITIES_S)

    log.info("done: %d succeeded, %d failed this run", succeeded, failed)
    log.info("results  -> %s", RESULTS)
    if failed:
        log.info("failures -> %s", FAILURES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

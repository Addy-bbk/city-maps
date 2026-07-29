"""Get all cities, reliably, so that no failure stops the entire run.

The primary differences between run_pilot.py and run_all.py are:

* Resume. If you stop (or crash) the run and restart it, all cities whose data is already in the results file will be ignored, 
avoiding repetition of prior data or requests to the Overpass servers.

* Isolation. In the case of an error, each city is wrapped in a try/except block, 
causing only a log entry for the error but allowing the rest of the run to continue with the next city instead of stopping.

* Politeness. To avoid hammering the public Overpass API, 
there is a brief delay between queries and the request timeout has been increased to allow larger cities sufficient time to respond.

* Provenance. All attempts, both successes and failures, are captured, allowing a complete report of how many cities were successfully completed, 
how many failed, and why they did so to also be generated.

Usage (from the project root, with the citymaps environment active):

    python scripts/run_all.py                 # process every city, resuming
    python scripts/run_all.py --restart       # ignore prior results, start over
    python scripts/run_all.py --limit 10      # process at most 10 new cities
"""

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import osmnx as ox

from citymaps import config, pipeline, validate
from citymaps.formats import read_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("run_all")

# Give large cities time to come back from Overpass, and pause between cities.
REQUEST_TIMEOUT_S = 300
PAUSE_BETWEEN_CITIES_S = 5

RESULTS = config.LOG_DIR / "results.csv"
FAILURES = config.LOG_DIR / "failures.csv"

# The full set of columns a successful record can contain, fixed in advance so
# the CSV header is stable no matter which city is written first.
RESULT_FIELDS = [
    "city", "query", "region", "morphology", "crs",
    "raw_nodes", "final_nodes", "final_edges", "reduction_pct",
    "n_nodes", "n_edges", "mean_degree", "edge_node_ratio",
    "connected", "n_components", "n_self_loops", "n_isolated",
    "within_planar_bound", "plausible_mean_degree", "passed",
    "is_planar", "witness_computed", "kuratowski_size", "file",
]


def load_done() -> set:
    """A collection of names that have already been marked as successful so that we can resume a run and bypass them."""
    if not RESULTS.exists():
        return set()
    with RESULTS.open() as fh:
        return {row["city"] for row in csv.DictReader(fh)}


def append_row(path: Path, fields: list, row: dict) -> None:
    """Add a single row to a CSV file. Add a header first when appending to a new file. When adding rows (as opposed to rewriting), 
    we can stop the run at any point and it will still be durable on disk by then."""
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
    ap.add_argument("--list", type=Path, default=config.CITY_LIST,
                    help="path to the city CSV (default: configured list)")
    args = ap.parse_args()

    ox.settings.requests_timeout = REQUEST_TIMEOUT_S

    if args.restart:
        for p in (RESULTS, FAILURES):
            p.unlink(missing_ok=True)
        log.info("restart: cleared previous results")

    cities = list(csv.DictReader(args.list.open()))
    done = load_done()
    todo = [c for c in cities if c["name"] not in done]
    if args.limit:
        todo = todo[: args.limit]

    log.info("%d cities total, %d already done, %d to attempt this run",
             len(cities), len(done), len(todo))

    succeeded = failed = 0
    for i, city in enumerate(todo, 1):
        name, query = city["name"], city["query"]
        log.info("[%d/%d] %s", i, len(todo), name)
        try:
            rec = pipeline.process_city(name, query)
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
        log.info("failures -> %s  (fix queries and re-run to retry them)", FAILURES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

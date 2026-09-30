"""Run bounded discovery batches and save a submission snapshot after each one.

Run from the repository root after installing the package. This command stops
at the target or the lead budget. A browser pause stops the driver as well.
"""

import argparse
import asyncio
import json
import shutil
from pathlib import Path

from rivyou.config import ROOT, CrawlConfig
from rivyou.db import Database, EmptyQueueError
from rivyou.pipeline import Pipeline
from rivyou.report import project, records, snapshot_files
from rivyou.sources import discover_source


def checkpoint(db, output):
    rows = project(db.all_candidates())
    if not any(row.get("store") for row in rows):
        print(
            "No collected records yet; existing snapshot files were preserved.",
            flush=True,
        )
        return 0
    output.mkdir(parents=True, exist_ok=True)
    for name, body in snapshot_files(rows, db.runs()).items():
        (output / name).write_bytes(body.encode("utf-8"))
    count = len(records(rows))
    print(
        json.dumps({"accepted": count, "candidates": len(rows), "output": str(output)}),
        flush=True,
    )
    return count


async def run_batch(db, operation, workers, limit):
    config = CrawlConfig(
        operation=operation,
        max_bytes=8 * 1024 * 1024,
        max_pages=11 if operation == "enrich" else 7,
        concurrency=workers,
    )
    try:
        rid = await Pipeline(db, config).run(limit)
    except EmptyQueueError:
        return True
    run = next(r for r in db.runs() if r["id"] == rid)
    print(
        json.dumps(
            {"run_id": rid, "status": run["status"], "completed": run["completed"]}
        ),
        flush=True,
    )
    return run["status"] == "completed"


async def build(args):
    db = Database()
    if any(r["status"] == "running" for r in db.runs()):
        raise ValueError(
            "A run is already active. Finish or pause it before starting this command."
        )
    offset = args.start_offset
    while True:
        if shutil.disk_usage(db.path.parent).free < 1024**3:
            raise OSError(
                "Less than 1 GiB is free. Free disk space before collecting more evidence."
            )
        for operation in ("collect", "enrich"):
            if not await run_batch(db, operation, args.workers, 1000):
                checkpoint(db, args.output)
                print(
                    "Stopped after a paused or incomplete run. Resume that run explicitly.",
                    flush=True,
                )
                return False
        if checkpoint(db, args.output) >= args.target:
            return True
        if any(row["status"] == "queued" for row in db.all_candidates()):
            continue
        if offset >= args.max_leads:
            print(
                "Lead budget reached. The snapshot contains only qualifying records.",
                flush=True,
            )
            return False
        count = min(args.batch_size, args.max_leads - offset)
        manifest = await discover_source(
            db, "dukaan", offset, count, cached=args.cached
        )
        print(
            json.dumps(
                {
                    "discovery_offset": offset,
                    "selected": manifest["selected"],
                    **manifest["result"],
                }
            ),
            flush=True,
        )
        offset += count
        if not manifest["selected"]:
            return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--max-leads", type=int, default=3500)
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--batch-size", type=int, choices=range(1, 1001), default=500)
    parser.add_argument("--workers", type=int, choices=range(1, 17), default=8)
    parser.add_argument("--cached", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs")
    args = parser.parse_args()
    if not 0 <= args.start_offset <= args.max_leads <= 10000 or args.target < 1:
        parser.error(
            "Use 0 <= start-offset <= max-leads <= 10000 and a positive target."
        )
    raise SystemExit(0 if asyncio.run(build(args)) else 2)


if __name__ == "__main__":
    main()

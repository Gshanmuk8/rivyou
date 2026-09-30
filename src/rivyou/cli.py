"""CLI for reproducible runs and a browser workbench over the same database."""

import argparse
import asyncio
import json
from pathlib import Path

from .config import ROOT, CrawlConfig
from .db import Database
from .discovery import discover_cdx, import_cdx_file, import_json
from .pipeline import Pipeline
from .report import (
    project,
    records,
    snapshot_files,
    statistics,
)


def main():
    parser = argparse.ArgumentParser(
        description="Discover and inspect Indian Shopify stores."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Open the local workbench")
    serve.add_argument("--port", type=int, default=8765)
    seed = sub.add_parser("import", help="Import attributed candidates")
    seed.add_argument("path", type=Path)
    run = sub.add_parser("collect", help="Collect queued candidates")
    run.add_argument("--limit", type=int, default=20)
    run.add_argument("--resume")
    run.add_argument("--max-mib", type=int, default=8, choices=range(1, 17))
    run.add_argument("--workers", type=int, default=8, choices=range(1, 17))
    enrich = sub.add_parser(
        "enrich", help="One bounded follow-up for unresolved candidates"
    )
    enrich.add_argument("--limit", type=int, default=300)
    enrich.add_argument("--max-mib", type=int, default=8, choices=range(1, 17))
    enrich.add_argument("--workers", type=int, default=8, choices=range(1, 17))
    sources = sub.add_parser(
        "discover-source", help="Import a bounded public lead source"
    )
    sources.add_argument("source", choices=["dukaan", "eachspy"])
    sources.add_argument("--offset", type=int, default=0)
    sources.add_argument("--limit", type=int, default=300)
    sources.add_argument(
        "--cached",
        action="store_true",
        help="Use a previously downloaded, checksum-verified source",
    )
    out = sub.add_parser("export", help="Export current verified records and evidence")
    out.add_argument("--output", type=Path, default=ROOT / "outputs")
    sub.add_parser("status")
    refine = sub.add_parser(
        "refine", help="Offline rule-7 to rule-8 contact/runtime migration"
    )
    refine.add_argument(
        "--source-run", help="Completed full replay to use as the unchanged baseline"
    )
    replay = sub.add_parser(
        "reprocess",
        help="Re-evaluate saved pages with current extraction rules; only missing logos may be fetched",
    )
    replay.add_argument("--limit", type=int, default=1000)
    replay.add_argument(
        "--offline", action="store_true", help="Do not request uncached logos"
    )
    replay.add_argument(
        "--processes",
        type=int,
        choices=range(1, 5),
        default=1,
        help="CPU processes for --offline replay; allow memory for each parser",
    )
    cc = sub.add_parser(
        "discover-cc", help="Bounded CDX lookup for a narrow hostname/path prefix"
    )
    cc.add_argument("--crawl", required=True)
    cc.add_argument("--prefix", required=True)
    cc.add_argument("--limit", type=int, default=100)
    saved = sub.add_parser(
        "import-cdx", help="Import saved Common Crawl JSONL URL records"
    )
    saved.add_argument("path", type=Path)
    saved.add_argument("--source-url", required=True)
    args = parser.parse_args()
    db = Database()
    if args.command == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(db), host="127.0.0.1", port=args.port)
    elif args.command == "import":
        print(json.dumps(import_json(db, args.path), indent=2))
    elif args.command == "collect":
        config = CrawlConfig(
            max_bytes=args.max_mib * 1024 * 1024, concurrency=args.workers
        )
        rid = asyncio.run(
            Pipeline(db, config).run(max(1, min(args.limit, 1000)), args.resume)
        )
        print(json.dumps({"run_id": rid, "runs": db.runs()}, indent=2))
    elif args.command == "discover-source":
        from .sources import discover_source

        print(
            json.dumps(
                asyncio.run(
                    discover_source(
                        db, args.source, args.offset, args.limit, cached=args.cached
                    )
                ),
                indent=2,
            )
        )
    elif args.command == "enrich":
        config = CrawlConfig(
            operation="enrich",
            max_pages=11,
            max_bytes=args.max_mib * 1024 * 1024,
            concurrency=args.workers,
        )
        rid = asyncio.run(Pipeline(db, config).run(max(1, min(args.limit, 1000))))
        print(json.dumps({"run_id": rid}, indent=2))
    elif args.command == "reprocess":
        if args.processes > 1:
            if not args.offline:
                parser.error("Parallel reprocessing requires --offline.")
            from .replay import parallel_replay

            print(asyncio.run(parallel_replay(db, args.limit, args.processes)))
            return
        print(
            asyncio.run(
                Pipeline(db, CrawlConfig(operation="replay", offline=args.offline)).run(
                    args.limit
                )
            )
        )
    elif args.command == "refine":
        from .refine import refine_saved

        print(refine_saved(db, args.source_run))
    elif args.command == "status":
        print(json.dumps(statistics(project(db.all_candidates()), db.runs()), indent=2))
    elif args.command == "discover-cc":
        print(
            json.dumps(
                asyncio.run(discover_cdx(db, args.crawl, args.prefix, args.limit)),
                indent=2,
            )
        )
    elif args.command == "import-cdx":
        print(json.dumps(import_cdx_file(db, args.path, args.source_url), indent=2))
    elif args.command == "export":
        rows = project(db.all_candidates())
        args.output.mkdir(parents=True, exist_ok=True)
        payloads = snapshot_files(rows, db.runs())
        for name, body in payloads.items():
            # Match the manifest bytes exactly, including on Windows.
            (args.output / name).write_bytes(body.encode("utf-8"))
        print(f"Exported {len(records(rows))} records to {args.output}")


if __name__ == "__main__":
    main()

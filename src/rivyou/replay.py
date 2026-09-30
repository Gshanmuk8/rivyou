"""Optional CPU processes for offline replay; each uses the same extraction path."""

import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .config import CrawlConfig
from .db import Database
from .fetch import Fetcher
from .models import Store
from .pipeline import Pipeline


def replay_candidate(db_path: str, rid: str, candidate: dict, config: dict):
    """Spawn-safe worker. SQLite transactions serialize its short writes."""
    db = Database(Path(db_path))
    settings = CrawlConfig(**config)
    if settings.operation != "replay" or not settings.offline:
        raise ValueError("Process replay only accepts offline replay configuration.")

    async def apply():
        async with Fetcher(settings, cache_dir=db.path.parent / "cache") as fetcher:
            await Pipeline(db, settings).collect_one(rid, candidate, fetcher)

    try:
        asyncio.run(apply())
    except Exception as exc:  # noqa: BLE001 - Same per-record failure boundary as live collection.
        store = Store(
            store_id=candidate["id"],
            domain_url=candidate["url"],
            status="error",
            reason=f"{type(exc).__name__}: {str(exc)[:250]}",
        )
        db.save_result(rid, candidate["id"], store.model_dump())


async def parallel_replay(db: Database, limit: int, processes: int = 2):
    if not 1 <= processes <= 4:
        raise ValueError("Choose one to four replay processes.")
    config = CrawlConfig(operation="replay", offline=True, concurrency=processes)
    rid, candidates = db.start_run(config.to_dict(), limit)
    slots = asyncio.Semaphore(processes)

    async def heartbeat():
        while True:
            db.heartbeat(rid)
            await asyncio.sleep(5)

    beat = asyncio.create_task(heartbeat())
    try:
        with ProcessPoolExecutor(
            max_workers=processes, mp_context=multiprocessing.get_context("spawn")
        ) as pool:

            async def worker(candidate):
                async with slots:
                    if db.pause_requested(rid):
                        return
                    await asyncio.get_running_loop().run_in_executor(
                        pool,
                        replay_candidate,
                        str(db.path),
                        rid,
                        candidate,
                        config.to_dict(),
                    )

            await asyncio.gather(*(worker(candidate) for candidate in candidates))
        db.finish_run(rid, "cancelled" if db.pause_requested(rid) else "completed")
    except asyncio.CancelledError:
        db.finish_run(
            rid,
            "interrupted",
            "Offline replay interrupted; saved observations are reusable.",
        )
        raise
    except Exception as exc:
        db.finish_run(rid, "failed", str(exc)[:500])
        raise
    finally:
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)
    return rid

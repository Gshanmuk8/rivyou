"""Explicitly attributed candidate ingestion; a lead is never verification."""

import json
from pathlib import Path
from urllib.parse import urlencode

from .config import CrawlConfig
from .db import Database
from .fetch import Fetcher
from .models import now


def import_json(db: Database, path: Path):
    values = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(values, list) or len(values) > 50000:
        raise ValueError(
            "Expected an array of up to 50,000 attributed candidate objects."
        )
    entries = []
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("Each candidate must be a JSON object.")
        if "candidate_url" in item:
            sources = item.get("sources")
            if not isinstance(sources, list) or not sources:
                raise ValueError("A saved candidate needs its discovery sources.")
            for source in sources:
                if not isinstance(source, dict):
                    raise ValueError("Each discovery source must be a JSON object.")
                entries.append(
                    {
                        "url": item["candidate_url"],
                        "source": source.get("name", ""),
                        "source_url": source.get("source_url", ""),
                    }
                )
        else:
            entries.append(item)
    if len(entries) > 50000:
        raise ValueError("Use at most 50,000 candidate/source pairs per import.")
    for entry in entries:
        if any(
            not isinstance(entry.get(key, ""), str)
            for key in ("url", "source", "source_url")
        ):
            raise ValueError("Candidate URLs and source attribution must be text.")
    # A saved result's status/evidence never become a new verification pass.
    return db.import_candidates(entries)


async def discover_cdx(db: Database, crawl: str, prefix: str, limit: int = 100):
    import re

    if not re.fullmatch(r"CC-MAIN-\d{4}-\d{2}", crawl):
        raise ValueError("Use a published Common Crawl ID, such as CC-MAIN-2026-XX.")
    if (
        not re.fullmatch(r"[a-z0-9][a-z0-9.-]+\.[a-z]{2,}/[^?]*", prefix, re.IGNORECASE)
        or "*" in prefix[: prefix.index("/")]
    ):
        raise ValueError(
            "CDX is for a narrow hostname/path prefix. Use a local URL Index partition for bulk discovery."
        )
    limit = min(max(1, limit), 200)
    query = urlencode(
        {
            "url": prefix + "*",
            "output": "json",
            "filter": "status:200",
            "collapse": "urlkey",
        }
    )
    url = f"https://index.commoncrawl.org/{crawl}-index?{query}"
    config = CrawlConfig(
        concurrency=1, delay_seconds=3, retries=1, max_bytes=2 * 1024 * 1024
    )
    async with Fetcher(config, cache_dir=db.path.parent / "cache") as fetcher:
        fetched = await fetcher.get(url, kind="discovery")
    if fetched.outcome != "ok":
        raise ValueError(
            f"Index query was deferred: {fetched.outcome} {fetched.detail}"
        )
    entries = []
    for line in fetched.text.splitlines():
        try:
            item = json.loads(line)
            entries.append(
                {
                    "url": item["url"],
                    "source": f"Common Crawl {crawl}",
                    "source_url": url,
                }
            )
        except (ValueError, KeyError):
            continue
        if len(entries) >= limit:
            break
    result = db.import_candidates(entries)
    manifest = {
        "source_url": url,
        "crawl": crawl,
        "prefix": prefix,
        "retrieved_at": now(),
        "bytes": len(fetched.body),
        "content_hash": fetched.digest,
        "result": result,
        "limit": limit,
        "complete": False,
        "note": "Bounded query, not an exhaustive index scan.",
    }
    folder = db.path.parent / "discovery"
    folder.mkdir(exist_ok=True)
    (folder / f"cdx-{crawl}-{fetched.digest[:12]}.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def import_cdx_file(db: Database, path: Path, source_url: str, limit: int = 5000):
    entries = []
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            entries.append(
                {
                    "url": item["url"],
                    "source": "Common Crawl saved URL records",
                    "source_url": source_url,
                }
            )
            if len(entries) >= limit:
                break
    return db.import_candidates(entries)

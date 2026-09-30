"""Bounded public lead sources. All acceptance decisions come from live stores."""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .cache import read_snapshot
from .config import ROOT, CrawlConfig
from .db import Database
from .fetch import Fetcher
from .models import now
from .urls import normalize_url

SOURCES = {
    "dukaan": {
        "name": "TeamDukaan public performance list · commit b9be3b56",
        "url": "https://raw.githubusercontent.com/TeamDukaan/performance/b9be3b56f962538ba153ab196ba3ac5014561c56/shopify%20stores%20-%20shopify.csv",
        "page": "https://github.com/TeamDukaan/performance/blob/b9be3b56f962538ba153ab196ba3ac5014561c56/shopify%20stores%20-%20shopify.csv",
        "parser": "lines",
        "note": "Historical public URL leads, not current platform/country proof. No explicit repository license was found. Raw source is cached locally, not redistributed as our dataset.",
    },
    "eachspy": {
        "name": "EachSpy public India directory",
        "url": "https://www.eachspy.com/shopify/stores-in-india/",
        "page": "https://www.eachspy.com/shopify/stores-in-india/",
        "parser": "store_tables",
        "note": "Only public domain names in Store tables are used as leads. Directory contacts, descriptions, logos and classifications are not copied into results.",
    },
}


def parse_leads(text: str, parser: str) -> list[str]:
    if parser == "lines":
        values = [line.strip().strip('"') for line in text.splitlines()]
    elif parser == "store_tables":
        soup = BeautifulSoup(text, "lxml")
        values = []
        for table in soup.select("table"):
            header = table.select_one("th")
            if not header or header.get_text(strip=True).lower() != "store":
                continue
            for row in table.select("tr"):
                cell = row.select_one("td")
                if cell:
                    match = re.search(
                        r"\b(?:[a-z0-9][a-z0-9-]*\.)+[a-z]{2,24}\b",
                        cell.get_text(" ", strip=True),
                        re.IGNORECASE,
                    )
                    if match:
                        values.append(match.group())
    else:
        raise ValueError("Unknown lead parser.")
    urls = []
    for value in values:
        try:
            urls.append(normalize_url(value, homepage=True))
        except ValueError:
            continue
    return list(dict.fromkeys(urls))


async def discover_source(
    db: Database,
    source: str,
    offset: int = 0,
    limit: int = 300,
    manifest_dir: Path | None = None,
    cached: bool = False,
) -> dict:
    if source not in SOURCES or not 1 <= limit <= 10000 or offset < 0:
        raise ValueError(
            "Choose a supported source, nonnegative offset and limit 1–10000."
        )
    spec = SOURCES[source]
    folder = manifest_dir or ROOT / "data" / "discovery"
    original_date = None
    if cached:
        from .fetch import Fetched

        for path in sorted(folder.glob(f"{source}-*.json")):
            previous = json.loads(path.read_bytes())
            if previous.get("download_url") != spec["url"]:
                continue
            body = read_snapshot(db.path.parent / "cache", previous["content_hash"])
            if body is not None:
                original_date = previous["retrieved_at"]
                fetched = Fetched(spec["url"], spec["url"], 200, "ok", body)
                break
        else:
            raise ValueError(
                "No matching saved source. Run discovery without --cached first."
            )
    else:
        # Source responses and robots are cached independently of merchant runs.
        async with Fetcher(
            CrawlConfig(concurrency=1, delay_seconds=2, retries=1),
            cache_dir=db.path.parent / "cache",
        ) as fetcher:
            fetched = await fetcher.get(spec["url"], kind="discovery")
        if fetched.outcome != "ok":
            raise ValueError(f"Source deferred: {fetched.outcome} {fetched.detail}")
    urls = parse_leads(fetched.text, spec["parser"])
    selected = urls[offset : offset + limit]
    result = db.import_candidates(
        [
            {"url": url, "source": spec["name"], "source_url": spec["page"]}
            for url in selected
        ]
    )
    manifest = {
        "source": source,
        "name": spec["name"],
        "source_url": spec["page"],
        "download_url": spec["url"],
        "retrieved_at": original_date or now(),
        "imported_at": now(),
        "used_saved_source": cached,
        "content_hash": fetched.digest,
        "bytes": len(fetched.body),
        "available_unique_urls": len(urls),
        "offset": offset,
        "limit": limit,
        "selected": len(selected),
        "result": result,
        "note": spec["note"],
    }
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{source}-{offset}-{limit}.json").write_bytes(
        json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    )
    return manifest

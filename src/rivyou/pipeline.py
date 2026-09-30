"""Collection orchestration. Pure extraction is separate from network and storage."""

import asyncio
import json
from io import BytesIO

from lxml import etree
from PIL import Image, ImageColor, UnidentifiedImageError

from .cache import read_snapshot
from .config import CrawlConfig
from .db import Database
from .extract import Page, extract, logo_candidates, select_links
from .fetch import Fetched, Fetcher
from .models import Store
from .urls import same_site


def logo_background(body: bytes, extension: str) -> str:
    if extension == "svg":
        import re

        colors = re.findall(rb'(?:fill|stroke)=["\']([^"\']+)', body.lower())
        # Some brand SVGs use class rules instead of presentation attributes.
        colors.extend(re.findall(rb"(?:fill|stroke)\s*:\s*([^;}\"']+)", body.lower()))
        brightness = []
        for color in colors:
            try:
                rgb = ImageColor.getrgb(color.decode("ascii").strip())
                brightness.append(sum(rgb[:3]) / 3)
            except (ValueError, UnicodeDecodeError):
                continue  # Gradients and 'none' have no single foreground colour.
        return (
            "dark"
            if brightness and sum(brightness) / len(brightness) > 210
            else "light"
        )
    with Image.open(BytesIO(body)).convert("RGBA") as image:
        image.thumbnail((50, 50))
        pixels = [p for p in image.getdata() if p[3] > 100]
        return (
            "dark"
            if pixels and sum(sum(p[:3]) / 3 for p in pixels) / len(pixels) > 210
            else "light"
        )


def safe_logo(body: bytes, content_type: str) -> tuple[bytes, str] | None:
    if content_type == "image/svg+xml" or body.lstrip().startswith(b"<svg"):
        try:
            parser = etree.XMLParser(
                resolve_entities=False, no_network=True, recover=False
            )
            root = etree.fromstring(body, parser)
            if etree.QName(root).localname != "svg":
                return None
            for element in list(root.iter()):
                tag = etree.QName(element).localname
                unsafe_style = tag == "style" and (
                    "@import" in (element.text or "").lower()
                    or "url(" in (element.text or "").lower()
                )
                if (
                    tag in {"script", "foreignObject", "image", "animate", "set"}
                    or unsafe_style
                ):
                    if element.getparent() is not None:
                        element.getparent().remove(element)
                    continue
                for key, value in list(element.attrib.items()):
                    external_ref = etree.QName(key).localname in {
                        "href",
                        "src",
                    } and not value.startswith("#")
                    if (
                        etree.QName(key).localname.lower().startswith("on")
                        or ("url(" in value.lower() and "url(#" not in value.lower())
                        or external_ref
                    ):
                        del element.attrib[key]
            return etree.tostring(root), "svg"
        except (etree.XMLSyntaxError, ValueError):
            return None
    try:
        with Image.open(BytesIO(body)) as image:
            if (
                image.width < 12
                or image.height < 12
                or image.width * image.height > 20_000_000
            ):
                return None
            image.thumbnail((800, 400))
            output = BytesIO()
            image.convert("RGBA").save(output, format="PNG")
            return output.getvalue(), "png"
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None


class Pipeline:
    def __init__(self, db: Database, config: CrawlConfig | None = None):
        self.db = db
        self.config = config or CrawlConfig()
        self.cancel_requested = False
        self.active_id = None

    def should_pause(self, rid: str) -> bool:
        return self.cancel_requested or self.db.pause_requested(rid)

    async def collect_one(self, rid: str, candidate: dict, fetcher: Fetcher):
        cid, url = candidate["id"], candidate["url"]
        self.db.item_started(rid, cid)
        pages, seen = [], set()
        # Resume uses the successful HTML already fetched in this run.
        source_run = (
            self.db.latest_page_run(cid)
            if self.config.operation in {"replay", "enrich"}
            else rid
        )
        for row in self.db.cached_pages(source_run or rid, cid):
            body = read_snapshot(fetcher.cache_dir, row["content_hash"])
            if (
                row["final_url"] in seen
                or body is None
                or "html" not in row["content_type"]
            ):
                continue
            result = Fetched(
                row["url"],
                row["final_url"],
                status_code=200,
                outcome="ok",
                body=body,
                content_type=row["content_type"],
                observed_at=row["observed_at"],
            )
            pages.append(Page.from_fetch(result))
            seen.add(row["final_url"])
            if source_run != rid:
                # Keep the complete evidence set together for future replay.
                # Reuse preserves the original observation date and hash.
                self.db.save_observation(rid, cid, result.observation("cached_page"))
        if not pages and self.config.operation == "replay":
            self.db.save_result(rid, cid, json.loads(candidate["store_json"]))
            return
        if not pages:
            result = await fetcher.get(url, context=(rid, cid))
            if result.outcome != "ok" or "html" not in result.content_type:
                store = Store(
                    store_id=cid,
                    domain_url=url,
                    status="blocked"
                    if result.outcome == "robots_blocked"
                    else "unreachable",
                    reason=result.detail
                    or f"Homepage returned {result.status_code or result.outcome}",
                )
                self.db.save_result(rid, cid, store.model_dump())
                return
            pages.append(Page.from_fetch(result))
            seen.add(result.final_url)
        pending = select_links(pages[0])
        if self.config.operation == "enrich":
            from urllib.parse import urljoin

            # Public policy routes still pass through the robots-aware fetcher.
            pending = [
                urljoin(pages[0].url, path)
                for path in (
                    "/policies/contact-information",
                    "/policies/terms-of-service",
                    "/policies/privacy-policy",
                    "/pages/contact-us",
                )
            ] + pending
        for page in pages[1:]:
            pending.extend(select_links(page))
        pending = list(dict.fromkeys(pending))
        attempted = len(pages)
        page_limit = self.config.max_pages
        if self.config.operation == "enrich":
            page_limit = min(page_limit, attempted + 4)
        while (
            self.config.operation != "replay"
            and pending
            and attempted < page_limit
            and not self.should_pause(rid)
        ):
            target = pending.pop(0)
            if target in seen:
                continue
            seen.add(target)
            attempted += 1
            result = await fetcher.get(target, context=(rid, cid))
            if (
                result.outcome == "ok"
                and "html" in result.content_type
                and same_site(pages[0].url, result.final_url)
            ):
                if result.final_url != target and result.final_url in {
                    p.url for p in pages
                }:
                    continue
                page = Page.from_fetch(result)
                pages.append(page)
                for link in select_links(page):
                    if link not in seen and link not in pending:
                        pending.append(link)
        if self.should_pause(rid):
            return  # Saved observations will be reused on resume.
        store = await asyncio.to_thread(extract, pages, cid, url)
        logos_dir = self.db.path.parent / "logos"
        logos_dir.mkdir(exist_ok=True)
        for _, logo_url, rule in logo_candidates(pages[0])[:3]:
            if self.should_pause(rid):
                return
            cached = self.db.cached_logo(cid, logo_url)
            cached_body = (
                read_snapshot(fetcher.cache_dir, cached["content_hash"])
                if cached
                else None
            )
            if (
                self.config.operation in {"replay", "enrich"}
                and cached_body is not None
            ):
                result = Fetched(
                    logo_url,
                    cached["final_url"],
                    status_code=200,
                    outcome="ok",
                    body=cached_body,
                    content_type=cached["content_type"],
                    observed_at=cached["observed_at"],
                )
            else:
                if self.config.offline:
                    continue
                result = await fetcher.get(logo_url, kind="logo", context=(rid, cid))
            if result.outcome != "ok" or not result.content_type.startswith("image/"):
                continue
            safe = safe_logo(result.body, result.content_type)
            if safe:
                path = logos_dir / f"{cid}.{safe[1]}"
                path.write_bytes(safe[0])
                store.logo_url = logo_url
                store.logo_path = str(path.name)
                store.logo_background = logo_background(*safe)
                store.missing.pop("logo_url", None)
                store.evidence.append(
                    pages[0].evidence(
                        "logo_url",
                        logo_url,
                        rule,
                        "Brand image selected from the homepage and validated as an image.",
                    )
                )
                break
        self.db.save_result(rid, cid, store.model_dump())

    async def execute(self, rid: str, candidates: list[dict]):
        self.active_id = rid
        self.cancel_requested = False

        async def beat():
            while True:
                self.db.heartbeat(rid)
                await asyncio.sleep(5)

        heartbeat = asyncio.create_task(beat())
        limit = asyncio.Semaphore(self.config.concurrency)

        async def worker(candidate, fetcher):
            async with limit:
                if self.should_pause(rid):
                    return
                try:
                    await self.collect_one(rid, candidate, fetcher)
                except Exception as exc:  # noqa: BLE001 - Persist candidate failure without losing the batch.
                    store = Store(
                        store_id=candidate["id"],
                        domain_url=candidate["url"],
                        status="error",
                        reason=f"{type(exc).__name__}: {str(exc)[:250]}",
                    )
                    self.db.save_result(rid, candidate["id"], store.model_dump())

        try:

            def observer(context, data):
                if context:
                    self.db.save_observation(*context, data)

            async with Fetcher(
                self.config, observer, cache_dir=self.db.path.parent / "cache"
            ) as fetcher:
                await asyncio.gather(*(worker(c, fetcher) for c in candidates))
            self.db.finish_run(
                rid, "cancelled" if self.should_pause(rid) else "completed"
            )
        except asyncio.CancelledError:
            self.db.finish_run(
                rid,
                "interrupted",
                "Process stopped; resume the run to reuse saved pages.",
            )
            raise
        except Exception as exc:
            self.db.finish_run(rid, "failed", str(exc)[:500])
            raise
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            self.active_id = None

    async def run(self, limit: int = 20, resume_id: str | None = None):
        rid, candidates = self.db.start_run(self.config.to_dict(), limit, resume_id)
        if resume_id:
            previous = next(r for r in self.db.runs() if r["id"] == rid)
            self.config = CrawlConfig(**previous["config"])
        await self.execute(rid, candidates)
        return rid

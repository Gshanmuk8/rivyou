"""Local, same-origin workbench. No cloud services or user accounts."""

import asyncio
import io
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import ROOT, CrawlConfig
from .db import Database, EmptyQueueError
from .pipeline import Pipeline
from .report import (
    audit_sample,
    export_csv,
    project,
    records,
    snapshot_files,
    statistics,
)


class ImportRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    domains: str = Field(min_length=1, max_length=200000)
    source: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=8, max_length=2000)


class RunRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=1000)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    decision: Literal["confirmed", "excluded", "needs_review"]
    note: str = Field(min_length=10, max_length=2000)
    reviewer: Literal["human", "agent"] = "human"


def create_app(db: Database | None = None) -> FastAPI:
    database = db or Database()
    pipeline = Pipeline(database)
    tasks = set()

    @asynccontextmanager
    async def lifespan(app):
        yield
        pipeline.cancel_requested = True
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="Rivyou · Store discovery", version="0.1.0", lifespan=lifespan)
    app.state.db, app.state.pipeline = database, pipeline
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def local_mutations(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if request.headers.get("x-rivyou-request") != "1" or (
                origin and origin != str(request.base_url).rstrip("/")
            ):
                return JSONResponse(
                    {"detail": "Use the local Rivyou interface."}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(EmptyQueueError)
    async def empty_queue(request, exc):
        return JSONResponse(
            {"detail": str(exc), "code": "empty_queue"}, status_code=409
        )

    @app.exception_handler(ValueError)
    async def bad_input(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/api/overview")
    def overview():
        rows = project(database.all_candidates())
        runs = database.runs()
        return statistics(rows, runs)

    @app.get("/api/stores")
    def stores(
        q: str = "",
        status: str = "all",
        category: str = "",
        state: str = "",
        page: int = 1,
        per_page: int = 20,
    ):
        rows = project(database.all_candidates())
        filters = {
            "categories": sorted(
                {
                    r["store"]["category"]
                    for r in rows
                    if r["store"] and r["store"].get("category")
                }
            ),
            "states": sorted(
                {
                    r["store"]["state"]
                    for r in rows
                    if r["store"] and r["store"].get("state")
                }
            ),
        }
        if status != "all":
            if status == "attention":
                rows = [
                    r
                    for r in rows
                    if r["status"]
                    in {"review", "blocked", "unreachable", "error", "stale"}
                ]
            else:
                rows = [r for r in rows if r["status"] == status]
        if q:
            rows = [
                r
                for r in rows
                if q.lower()
                in " ".join(
                    [
                        r["url"],
                        (r["store"] or {}).get("name", ""),
                        (r["store"] or {}).get("state") or "",
                    ]
                ).lower()
            ]
        if category:
            rows = [
                r for r in rows if r["store"] and r["store"]["category"] == category
            ]
        if state:
            rows = [r for r in rows if r["store"] and r["store"]["state"] == state]
        order = {
            "accepted": 0,
            "review": 1,
            "queued": 2,
            "blocked": 3,
            "unreachable": 4,
            "excluded": 5,
            "duplicate": 6,
        }
        rows.sort(
            key=lambda r: (
                order.get(r["status"], 4),
                (r["store"] or {}).get("name", r["url"]).lower(),
            )
        )
        count = len(rows)
        per_page = max(1, min(per_page, 100))
        page = max(1, page)
        selected = rows[(page - 1) * per_page : page * per_page]
        for row in selected:
            if row["store"]:
                row["store"]["evidence_count"] = len(row["store"]["evidence"])
                row["store"].pop("evidence")
        return {
            "items": selected,
            "total": count,
            "page": page,
            "per_page": per_page,
            "filters": filters,
        }

    @app.get("/api/stores/{cid}")
    def detail(cid: str):
        value = database.detail(cid)
        if not value:
            raise HTTPException(404, "Store not found.")
        projected = next(
            r for r in project(database.all_candidates()) if r["id"] == cid
        )
        return {
            **value,
            **projected,
            "observations": value["observations"],
            "reviews": value["reviews"],
        }

    @app.get("/api/logos/{cid}")
    def logo(cid: str):
        if not all(c in "0123456789abcdef" for c in cid) or len(cid) != 16:
            raise HTTPException(404)
        with database.connect() as c:
            row = c.execute(
                "SELECT store_json FROM candidates WHERE id=?", (cid,)
            ).fetchone()
        store = json.loads(row["store_json"]) if row and row["store_json"] else {}
        filename = store.get("logo_path")
        if filename in {f"{cid}.png", f"{cid}.svg"}:
            path = database.path.parent / "logos" / filename
            if path.is_file():
                return FileResponse(
                    path,
                    media_type="image/svg+xml"
                    if filename.endswith(".svg")
                    else "image/png",
                )
        raise HTTPException(404, "No validated logo.")

    @app.post("/api/import")
    def import_candidates(body: ImportRequest):
        return database.import_candidates(
            [
                {
                    "url": line.strip(),
                    "source": body.source,
                    "source_url": body.source_url,
                }
                for line in body.domains.splitlines()
                if line.strip()
            ]
        )

    @app.post("/api/import-starter")
    def import_starter():
        from .discovery import import_json

        return import_json(database, ROOT / "data" / "seeds" / "shopify-editorial.json")

    def launch(limit=20, resume_id=None):
        config = CrawlConfig()
        rid, candidates = database.start_run(config.to_dict(), limit, resume_id)
        if resume_id:
            config = CrawlConfig(
                **next(r for r in database.runs() if r["id"] == rid)["config"]
            )
        pipeline.config = config
        task = asyncio.create_task(pipeline.execute(rid, candidates))
        tasks.add(task)

        def complete(t):
            tasks.discard(t)
            if not t.cancelled():
                t.exception()  # Consume exceptions; failed status is persisted.

        task.add_done_callback(complete)
        return {"run_id": rid, "candidates": len(candidates)}

    @app.post("/api/runs")
    async def start_run(body: RunRequest):
        return launch(body.limit)

    @app.get("/api/runs")
    def runs():
        return database.runs()

    @app.post("/api/runs/{rid}/cancel")
    def cancel_run(rid: str):
        database.request_pause(rid)
        return {
            "status": "stopping",
            "message": "Finishing the current request, then saving progress.",
        }

    @app.post("/api/runs/{rid}/resume")
    async def resume_run(rid: str):
        return launch(resume_id=rid)

    @app.post("/api/stores/{cid}/requeue")
    def requeue(cid: str):
        database.requeue(cid)
        return {"status": "queued"}

    @app.post("/api/stores/{cid}/review")
    def review(cid: str, body: ReviewRequest):
        database.review(cid, body.decision, body.note, body.reviewer)
        return {"status": "saved"}

    @app.get("/api/export/{format}")
    def export(format: str):
        rows = project(database.all_candidates())
        if format == "bundle":
            import zipfile

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, body in snapshot_files(rows, database.runs()).items():
                    archive.writestr(name, body.encode("utf-8"))
            return Response(
                buffer.getvalue(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": 'attachment; filename="rivyou-snapshot.zip"'
                },
            )
        elif format == "csv":
            content = export_csv(rows)
            media = "text/csv; charset=utf-8"
            name = "stores.csv"
        elif format == "json":
            content = json.dumps(records(rows), ensure_ascii=False, indent=2)
            media = "application/json"
            name = "stores.json"
        elif format == "evidence":
            content = "\n".join(
                json.dumps(
                    {
                        "store_id": r["id"],
                        "sources": r["sources"],
                        "review": r.get("review"),
                        **r["store"],
                    },
                    ensure_ascii=False,
                )
                for r in rows
                if r["status"] == "accepted"
            )
            media = "application/x-ndjson"
            name = "evidence.jsonl"
        elif format == "report":
            content = json.dumps(
                statistics(rows, database.runs()), ensure_ascii=False, indent=2
            )
            media = "application/json"
            name = "run-report.json"
        elif format == "audit":
            content = json.dumps(audit_sample(rows), ensure_ascii=False, indent=2)
            media = "application/json"
            name = "audit-sample.json"
        else:
            raise HTTPException(404, "Unknown export format.")
        return Response(
            content,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    static = Path(__file__).parent / "static"
    app.mount("/assets", StaticFiles(directory=static), name="assets")

    @app.get("/")
    def home():
        return FileResponse(static / "index.html")

    return app

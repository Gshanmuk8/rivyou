"""Small, transactional persistence layer. One connection per operation."""

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .config import WORK
from .models import now
from .urls import normalize_url


class EmptyQueueError(ValueError):
    """A new run was requested after all known candidates were processed."""


class Database:
    def __init__(self, path: Path | None = None):
        self.path = path or WORK / "rivyou.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS candidates(
                id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued', store_json TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS sources(
                candidate_id TEXT NOT NULL REFERENCES candidates(id), name TEXT NOT NULL,
                source_url TEXT NOT NULL, discovered_at TEXT NOT NULL,
                UNIQUE(candidate_id,name,source_url));
            CREATE TABLE IF NOT EXISTS runs(
                id TEXT PRIMARY KEY, status TEXT NOT NULL, started_at TEXT NOT NULL,
                finished_at TEXT, heartbeat TEXT NOT NULL, config TEXT NOT NULL, error TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON runs(status) WHERE status='running';
            CREATE TABLE IF NOT EXISTS run_items(
                run_id TEXT NOT NULL REFERENCES runs(id), candidate_id TEXT NOT NULL REFERENCES candidates(id),
                status TEXT NOT NULL DEFAULT 'pending', result_json TEXT, error TEXT,
                PRIMARY KEY(run_id,candidate_id));
            CREATE TABLE IF NOT EXISTS observations(
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
                url TEXT NOT NULL, final_url TEXT NOT NULL, kind TEXT NOT NULL, status_code INTEGER,
                outcome TEXT NOT NULL, observed_at TEXT NOT NULL, content_hash TEXT,
                bytes INTEGER NOT NULL DEFAULT 0, elapsed_ms INTEGER NOT NULL DEFAULT 0,
                detail TEXT NOT NULL DEFAULT '', content_type TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS reviews(
                id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id TEXT NOT NULL,
                decision TEXT NOT NULL, note TEXT NOT NULL, reviewer TEXT NOT NULL,
                reviewed_at TEXT NOT NULL, evidence_hash TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS observations_run ON observations(run_id,candidate_id);
            CREATE INDEX IF NOT EXISTS candidates_status ON candidates(status);
            CREATE TABLE IF NOT EXISTS run_controls(
                run_id TEXT PRIMARY KEY REFERENCES runs(id), pause_requested INTEGER NOT NULL DEFAULT 0);
            """)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def import_candidates(self, entries: list[dict]) -> dict:
        added, duplicate, errors = 0, 0, []
        with self.connect() as conn:
            for entry in entries:
                try:
                    url = normalize_url(entry["url"], homepage=True)
                    source = entry.get("source", "Manual import").strip()[:200]
                    source_url = entry.get("source_url", "").strip()[:2000]
                    if not source or not source_url:
                        raise ValueError(
                            "Every candidate needs a source name and source URL."
                        )
                    source_url = normalize_url(source_url)
                    cid = hashlib.sha256(url.encode()).hexdigest()[:16]
                    result = conn.execute(
                        "INSERT OR IGNORE INTO candidates(id,url,created_at) VALUES(?,?,?)",
                        (cid, url, now()),
                    )
                    added += result.rowcount
                    duplicate += int(not result.rowcount)
                    conn.execute(
                        "INSERT OR IGNORE INTO sources VALUES(?,?,?,?)",
                        (cid, source, source_url, now()),
                    )
                except (ValueError, KeyError) as exc:
                    errors.append({"url": entry.get("url", ""), "error": str(exc)})
        return {"added": added, "duplicates": duplicate, "errors": errors}

    def recover_stale(self):
        cutoff = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
        with self.connect() as conn:
            conn.execute(
                "UPDATE runs SET status='interrupted',error='Runner stopped responding' WHERE status='running' AND heartbeat<?",
                (cutoff,),
            )

    def start_run(
        self, config: dict, limit: int = 20, resume_id: str | None = None
    ) -> tuple[str, list[dict]]:
        self.recover_stale()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM runs WHERE status='running'").fetchone():
                raise ValueError("A collection is already running.")
            if resume_id:
                run = conn.execute(
                    "SELECT * FROM runs WHERE id=?", (resume_id,)
                ).fetchone()
                if not run or run["status"] not in {
                    "interrupted",
                    "cancelled",
                    "failed",
                }:
                    raise ValueError("This run cannot be resumed.")
                if json.loads(run["config"]).get("operation") == "refine":
                    raise ValueError(
                        "Repeat the offline refine command; this migration cannot resume as collection."
                    )
                if not conn.execute(
                    "SELECT 1 FROM run_items WHERE run_id=? AND status!='done'",
                    (resume_id,),
                ).fetchone():
                    raise ValueError("All candidates in this run are already finished.")
                conn.execute(
                    "UPDATE runs SET status='running',heartbeat=?,finished_at=NULL,error=NULL WHERE id=?",
                    (now(), resume_id),
                )
                conn.execute(
                    "UPDATE run_items SET status='pending' WHERE run_id=? AND status='running'",
                    (resume_id,),
                )
                rid = resume_id
                conn.execute("DELETE FROM run_controls WHERE run_id=?", (rid,))
            else:
                if config.get("operation") == "replay":
                    where = "store_json IS NOT NULL"
                elif config.get("operation") == "refine":
                    where = "json_extract(store_json,'$.rule_version') IN ('2026-09-30.7','2026-09-30.8')"
                elif config.get("operation") == "enrich":
                    where = """(status='unreachable' OR
                        (status='review' AND json_extract(store_json,'$.shopify')='verified')) AND id NOT IN (
                        SELECT i.candidate_id FROM run_items i JOIN runs r ON i.run_id=r.id
                        WHERE i.status='done' AND json_extract(r.config,'$.operation')='enrich'
                    )"""
                else:
                    where = "status='queued'"
                candidates = conn.execute(
                    "SELECT id FROM candidates WHERE "
                    + where
                    + " ORDER BY created_at,id LIMIT ?",
                    (limit,),
                ).fetchall()
                if not candidates:
                    raise EmptyQueueError(
                        "All known candidate domains have been checked. Add new sourced domains to continue."
                    )
                rid = uuid.uuid4().hex[:12]
                conn.execute(
                    "INSERT INTO runs(id,status,started_at,heartbeat,config) VALUES(?,'running',?,?,?)",
                    (rid, now(), now(), json.dumps(config)),
                )
                conn.executemany(
                    "INSERT INTO run_items(run_id,candidate_id) VALUES(?,?)",
                    [(rid, c["id"]) for c in candidates],
                )
            rows = conn.execute(
                "SELECT c.* FROM candidates c JOIN run_items i ON c.id=i.candidate_id WHERE i.run_id=? AND i.status='pending' ORDER BY c.id",
                (rid,),
            ).fetchall()
        return rid, [dict(row) for row in rows]

    def heartbeat(self, rid: str):
        with self.connect() as c:
            c.execute(
                "UPDATE runs SET heartbeat=? WHERE id=? AND status='running'",
                (now(), rid),
            )

    def request_pause(self, rid: str):
        """Persist the request so an API can pause a worker in another process."""
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            active = conn.execute(
                "SELECT 1 FROM runs WHERE id=? AND status='running'", (rid,)
            ).fetchone()
            if not active:
                raise ValueError(
                    "This collection is no longer running. Refresh to see its result."
                )
            conn.execute(
                "INSERT INTO run_controls VALUES(?,1) ON CONFLICT(run_id) DO UPDATE SET pause_requested=1",
                (rid,),
            )

    def pause_requested(self, rid: str) -> bool:
        with self.connect() as conn:
            return bool(
                conn.execute(
                    "SELECT 1 FROM run_controls WHERE run_id=? AND pause_requested=1",
                    (rid,),
                ).fetchone()
            )

    def finish_run(self, rid: str, status: str, error: str = ""):
        with self.connect() as c:
            c.execute(
                "UPDATE runs SET status=?,finished_at=?,heartbeat=?,error=? WHERE id=?",
                (status, now(), now(), error, rid),
            )

    def item_started(self, rid: str, cid: str):
        with self.connect() as c:
            c.execute(
                "UPDATE run_items SET status='running' WHERE run_id=? AND candidate_id=?",
                (rid, cid),
            )

    def save_result(self, rid: str, cid: str, store: dict):
        body = json.dumps(store, ensure_ascii=False)
        with self.connect() as c:
            c.execute(
                "UPDATE candidates SET status=?,store_json=?,updated_at=? WHERE id=?",
                (store["status"], body, now(), cid),
            )
            c.execute(
                "UPDATE run_items SET status='done',result_json=? WHERE run_id=? AND candidate_id=?",
                (body, rid, cid),
            )

    def save_observation(self, rid: str, cid: str, data: dict):
        fields = (
            "url",
            "final_url",
            "kind",
            "status_code",
            "outcome",
            "observed_at",
            "content_hash",
            "bytes",
            "elapsed_ms",
            "detail",
            "content_type",
        )
        with self.connect() as c:
            c.execute(
                "INSERT INTO observations(run_id,candidate_id,"
                + ",".join(fields)
                + ") VALUES("
                + ",".join("?" for _ in range(13))
                + ")",
                (rid, cid, *(data.get(f) for f in fields)),
            )

    def cached_pages(self, rid: str, cid: str) -> list[dict]:
        with self.connect() as c:
            rows = c.execute(
                "SELECT * FROM observations WHERE run_id=? AND candidate_id=? AND kind IN ('page','cached_page') AND outcome='ok' ORDER BY id",
                (rid, cid),
            ).fetchall()
            return [dict(r) for r in rows]

    def latest_page_run(self, cid: str) -> str | None:
        with self.connect() as c:
            row = c.execute(
                "SELECT run_id FROM observations WHERE candidate_id=? AND kind IN ('page','cached_page') AND outcome='ok' ORDER BY id DESC LIMIT 1",
                (cid,),
            ).fetchone()
            return row["run_id"] if row else None

    def cached_logo(self, cid: str, url: str) -> dict | None:
        with self.connect() as c:
            row = c.execute(
                "SELECT * FROM observations WHERE candidate_id=? AND kind='logo' AND url=? AND outcome='ok' ORDER BY id DESC LIMIT 1",
                (cid, url),
            ).fetchone()
            return dict(row) if row else None

    def all_candidates(self) -> list[dict]:
        with self.connect() as c:
            rows = c.execute(
                "SELECT * FROM candidates ORDER BY created_at,id"
            ).fetchall()
            sources = c.execute(
                "SELECT * FROM sources ORDER BY discovered_at"
            ).fetchall()
            reviews = c.execute("SELECT * FROM reviews ORDER BY id").fetchall()
        sm, rm = {}, {}
        for s in sources:
            sm.setdefault(s["candidate_id"], []).append(dict(s))
        for r in reviews:
            rm[r["candidate_id"]] = dict(r)
        result = []
        for row in rows:
            item = dict(row)
            item["store"] = (
                json.loads(item.pop("store_json")) if row["store_json"] else None
            )
            item["sources"] = sm.get(row["id"], [])
            item["review"] = rm.get(row["id"])
            result.append(item)
        return result

    def detail(self, cid: str) -> dict | None:
        item = next((x for x in self.all_candidates() if x["id"] == cid), None)
        if item:
            with self.connect() as c:
                item["observations"] = [
                    dict(x)
                    for x in c.execute(
                        "SELECT * FROM observations WHERE candidate_id=? ORDER BY id DESC LIMIT 100",
                        (cid,),
                    )
                ]
                item["reviews"] = [
                    dict(x)
                    for x in c.execute(
                        "SELECT * FROM reviews WHERE candidate_id=? ORDER BY id DESC",
                        (cid,),
                    )
                ]
        return item

    def runs(self) -> list[dict]:
        self.recover_stale()
        with self.connect() as c:
            rows = c.execute("""SELECT r.*,
              COALESCE((SELECT pause_requested FROM run_controls WHERE run_id=r.id),0) pause_requested,
              (SELECT COUNT(*) FROM run_items WHERE run_id=r.id) total,
              (SELECT COUNT(*) FROM run_items WHERE run_id=r.id AND status='done') completed,
              (SELECT COUNT(*) FROM observations WHERE run_id=r.id AND kind!='cached_page' AND status_code IS NOT NULL) requests,
              (SELECT COALESCE(SUM(bytes),0) FROM observations WHERE run_id=r.id AND kind!='cached_page') bytes
              FROM runs r ORDER BY started_at DESC""").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["config"] = json.loads(item["config"])
            result.append(item)
        return result

    def requeue(self, cid: str):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM runs WHERE status='running'").fetchone():
                raise ValueError("Wait for the active run before requeuing.")
            cur = c.execute("UPDATE candidates SET status='queued' WHERE id=?", (cid,))
            if not cur.rowcount:
                raise ValueError("Candidate not found.")

    def review(self, cid: str, decision: str, note: str, reviewer: str):
        item = self.detail(cid)
        if not item or not item["store"]:
            raise ValueError("Collect evidence before recording a review.")
        if decision not in {"confirmed", "excluded", "needs_review"}:
            raise ValueError("Invalid review decision.")
        store = item["store"]
        if decision == "confirmed" and (
            store["shopify"] != "verified" or store["india"] != "verified"
        ):
            raise ValueError(
                "Both verification checks must pass before confirming. Review cannot invent evidence."
            )
        digest = hashlib.sha256(
            json.dumps(store["evidence"], sort_keys=True).encode()
        ).hexdigest()
        with self.connect() as c:
            c.execute(
                "INSERT INTO reviews(candidate_id,decision,note,reviewer,reviewed_at,evidence_hash) VALUES(?,?,?,?,?,?)",
                (cid, decision, note, reviewer, now(), digest),
            )

"""One data projection for the UI and exports: freshness, reviews and dedup agree."""

import csv
import hashlib
import io
import json
from collections import Counter
from datetime import UTC, datetime, timedelta

from .config import RULE_VERSION, SCHEMA_VERSION
from .models import now

FIELDS = [
    "domain_url",
    "emails",
    "phones",
    "socials",
    "category",
    "description",
    "logo_url",
    "state",
]
OPTIONAL = [
    "emails",
    "phones",
    "socials",
    "category",
    "description",
    "logo_url",
    "state",
]


def evidence_hash(store):
    return hashlib.sha256(
        json.dumps(store.get("evidence", []), sort_keys=True).encode()
    ).hexdigest()


def project(candidates: list[dict]) -> list[dict]:
    result = []
    cutoff = datetime.now(UTC) - timedelta(days=7)
    for item in candidates:
        store = item.get("store")
        status = item["status"]
        review = item.get("review")
        effective_review = (
            review and store and review["evidence_hash"] == evidence_hash(store)
        )
        if store and status != "queued":
            if store["status"] == "accepted":
                required = [
                    e
                    for e in store.get("evidence", [])
                    if e["field"] in {"shopify", "india"}
                ]
                if datetime.fromisoformat(store["observed_at"]) < cutoff or any(
                    datetime.fromisoformat(e["observed_at"]) < cutoff for e in required
                ):
                    status = "stale"
                elif store["shopify"] != "verified" or store["india"] != "verified":
                    status = "review"
            if effective_review and review["decision"] in {"excluded", "needs_review"}:
                status = "excluded" if review["decision"] == "excluded" else "review"
        result.append(
            {**item, "status": status, "review_current": bool(effective_review)}
        )
    # Current, evidence-qualified stores only. Deterministic preference: custom
    # domain, then most complete record, then URL. Preserve duplicate evidence.
    accepted = [r for r in result if r["status"] == "accepted"]
    accepted.sort(
        key=lambda r: (
            "myshopify.com" in r["store"]["domain_url"],
            -sum(bool(r["store"].get(f)) for f in OPTIONAL),
            r["store"]["domain_url"],
        )
    )
    identities, urls = {}, {}
    for row in accepted:
        store = row["store"]
        identity = store.get("shop_identity")
        winner = identities.get(identity) if identity else None
        winner = winner or urls.get(store["domain_url"])
        if winner:
            row["status"] = "duplicate"
            row["duplicate_of"] = winner["id"]
            canonical = winner["store"]
            canonical["aliases"] = sorted(
                set(canonical["aliases"] + store["aliases"] + [store["domain_url"]])
            )
            for field in ("emails", "phones"):
                canonical[field] = sorted(set(canonical[field] + store[field]))
            for network, profiles in store["socials"].items():
                canonical["socials"][network] = sorted(
                    set(canonical["socials"].get(network, []) + profiles)
                )
            canonical["evidence"] += [
                e
                for e in store["evidence"]
                if e["field"] in {"emails", "phones", "socials"}
                and e not in canonical["evidence"]
            ]
        else:
            if identity:
                identities[identity] = row
            urls[store["domain_url"]] = row
    return result


def statistics(rows: list[dict], runs: list[dict]) -> dict:
    accepted = [r["store"] for r in rows if r["status"] == "accepted"]
    counts = Counter(r["status"] for r in rows)
    missing = {}
    for field in OPTIONAL:
        reasons = Counter(
            s.get("missing", {}).get(field, "not_found_in_allowed_pages")
            for s in accepted
            if not s.get(field)
        )
        total = sum(reasons.values())
        missing[field] = {
            "missing": total,
            "present": len(accepted) - total,
            "percent_missing": round(100 * total / len(accepted), 1)
            if accepted
            else None,
            "reasons": dict(reasons),
        }
    sources = {}
    for row in rows:
        for source in row["sources"]:
            bucket = sources.setdefault(
                source["name"],
                {
                    "name": source["name"],
                    "source_url": source["source_url"],
                    "candidates": 0,
                    "accepted": 0,
                    "collected": 0,
                },
            )
            bucket["candidates"] += 1
            bucket["accepted"] += int(row["status"] == "accepted")
            bucket["collected"] += int(row["store"] is not None)
    return {
        "generated_at": now(),
        "total": len(rows),
        "counts": dict(counts),
        "accepted": len(accepted),
        "target": 1000,
        "missingness": missing,
        "states": dict(Counter(s["state"] for s in accepted if s["state"])),
        "categories": dict(Counter(s["category"] for s in accepted if s["category"])),
        "sources": list(sources.values()),
        "requests": sum(r["requests"] for r in runs),
        "runs": len(runs),
        "audit_status": "Not independently audited",
        "rule_version": RULE_VERSION,
        "record_rule_versions": dict(
            Counter(s.get("rule_version", "unknown") for s in accepted)
        ),
        "schema_version": SCHEMA_VERSION,
    }


def records(rows):
    return [
        {
            **{f: row["store"].get(f) for f in FIELDS},
            "store_id": row["id"],
            "observed_at": row["store"]["observed_at"],
        }
        for row in rows
        if row["status"] == "accepted"
    ]


def csv_safe(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(
        ("\t", "\r", "\n")
    ):
        return "'" + text
    return text


def export_csv(rows):
    output = io.StringIO(newline="")
    columns = ["store_id", *FIELDS, "observed_at"]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in records(rows):
        writer.writerow({k: csv_safe(row.get(k)) for k in columns})
    return output.getvalue()


def audit_sample(rows, size=150, seed=20260929):
    import random

    population = sorted([r["id"] for r in rows if r["status"] == "accepted"])
    ids = random.Random(seed).sample(population, min(size, len(population)))
    return {
        "generated_at": now(),
        "seed": seed,
        "population": len(population),
        "sample_size": len(ids),
        "population_hash": hashlib.sha256("\n".join(population).encode()).hexdigest(),
        "note": "Unreviewed sample. No accuracy claim is implied.",
        "items": [
            {
                "store_id": sid,
                "shopify_and_india": None,
                "logo": None,
                "state": None,
                "contacts": None,
                "reviewer": None,
                "notes": "",
            }
            for sid in ids
        ],
    }


def snapshot_files(rows, runs):
    """Build all artifacts from the same in-memory dataset, with content hashes."""
    generated = now()
    stores = records(rows)
    evidence = [
        {
            "store_id": r["id"],
            "sources": r["sources"],
            "review": r.get("review"),
            **r["store"],
        }
        for r in rows
        if r["status"] == "accepted"
    ]
    snapshot_id = hashlib.sha256(
        json.dumps(
            {"stores": stores, "evidence": evidence}, sort_keys=True, ensure_ascii=False
        ).encode()
    ).hexdigest()[:16]
    report = {
        **statistics(rows, runs),
        "snapshot_id": snapshot_id,
        "generated_at": generated,
        "run_history": runs,
    }
    source_manifest = [
        {
            "candidate_id": r["id"],
            "candidate_url": r["url"],
            "status": r["status"],
            "sources": r["sources"],
        }
        for r in rows
    ]
    rejected = [
        {
            "store_id": r["id"],
            "domain_url": r["url"],
            "status": r["status"],
            "reason": (
                f"Duplicate of accepted store {r['duplicate_of']}."
                if r.get("duplicate_of")
                else "Evidence is older than the seven-day freshness window."
                if r["status"] == "stale"
                else "Queued for collection."
                if r["status"] == "queued"
                else f"Review: {r['review']['note']}"
                if r.get("review_current") and r["status"] in {"excluded", "review"}
                else (r.get("store") or {}).get("reason", "Not collected")
            ),
            "duplicate_of": r.get("duplicate_of"),
        }
        for r in rows
        if r["status"] != "accepted"
    ]
    files = {
        "stores.csv": export_csv(rows),
        "stores.json": json.dumps(stores, indent=2, ensure_ascii=False),
        "evidence.jsonl": "\n".join(
            json.dumps(e, ensure_ascii=False) for e in evidence
        ),
        "run-report.json": json.dumps(report, indent=2, ensure_ascii=False),
        "source-manifest.json": json.dumps(
            source_manifest, indent=2, ensure_ascii=False
        ),
        "unresolved.json": json.dumps(rejected, indent=2, ensure_ascii=False),
        "audit-sample.json": json.dumps(
            {**audit_sample(rows), "snapshot_id": snapshot_id}, indent=2
        ),
    }
    manifest = {
        "snapshot_id": snapshot_id,
        "generated_at": generated,
        "records": len(stores),
        "schema_version": SCHEMA_VERSION,
        "files": {
            name: hashlib.sha256(body.encode("utf-8")).hexdigest()
            for name, body in files.items()
        },
    }
    files["manifest.json"] = json.dumps(manifest, indent=2)
    return files

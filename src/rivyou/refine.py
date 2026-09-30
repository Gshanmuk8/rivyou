"""Narrow offline migration from rule 7 to 8, reusing unchanged decisions.

Only email/profile validation, logo scope and the runtime-asset requirement changed. Reading
the stored values and, where needed, a cached HTML tag is sufficient for this
transition. A full replay remains the path for other extraction-rule changes.
"""

import json
import re
from urllib.parse import unquote, urljoin, urlsplit

from lxml import etree, html

from .cache import read_snapshot
from .config import RULE_VERSION, CrawlConfig
from .extract import EMAIL, runtime_asset, social_link, valid_email
from .models import Store
from .urls import same_site


def refine_store(store: dict, cached_pages, cache_dir) -> dict:
    if store["rule_version"] not in {"2026-09-30.7", "2026-09-30.8"}:
        raise ValueError("This migration requires a completed rule-7 replay.")
    store = json.loads(json.dumps(store))
    trees = {}

    def cached_tree(digest):
        if digest not in trees:
            body = read_snapshot(cache_dir, digest)
            try:
                trees[digest] = html.fromstring(body) if body else None
            except (etree.ParserError, ValueError):
                trees[digest] = None
        return trees[digest]

    # A copied href can disagree with the address actually shown to a reader.
    # Keep the displayed address; do not treat that contradictory href as a contact.
    for proof in store["evidence"]:
        if proof["field"] != "emails" or proof["rule"] != "mailto_link":
            continue
        tree = cached_tree(proof["content_hash"])
        if tree is None:
            continue
        matching, consistent = False, False
        for anchor in tree.xpath("//a[@href]"):
            href = anchor.get("href", "")
            if not href.lower().startswith("mailto:"):
                continue
            targets = [x.lower() for x in EMAIL.findall(unquote(href.split("?", 1)[0]))]
            if proof["value"] not in targets:
                continue
            matching = True
            shown = [x.lower() for x in EMAIL.findall(anchor.text_content())]
            if not shown or proof["value"] in shown:
                consistent = True
        if matching and not consistent:
            proof["rule"] = "contradictory_mailto_omitted"
    supported = {
        e["value"]
        for e in store["evidence"]
        if e["field"] == "emails" and e["rule"] != "contradictory_mailto_omitted"
    }
    # Older rules mistook footer classes containing "logo" for a header, and
    # treated another company's homepage as this merchant's home link.
    for proof in store["evidence"]:
        if proof["field"] != "logo_url" or proof["rule"] not in {
            "header_brand_image",
            "logo_attribute",
        }:
            continue
        tree = cached_tree(proof["content_hash"])
        if tree is None:
            continue
        matched, eligible = False, False
        for img in tree.xpath("//img"):
            sources = [img.get("src", ""), img.get("data-src", "")]
            for key in ("srcset", "data-srcset"):
                sources.extend(
                    part.strip().split(" ")[0]
                    for part in img.get(key, "").split(",")
                    if part.strip()
                )
            if store["logo_url"] not in {
                urljoin(proof["source_url"], s) for s in sources if s
            }:
                continue
            matched = True
            parents = list(img.iterancestors())
            header = any(
                p.tag == "header" or re.search("header", p.get("class", ""), re.I)
                for p in parents
            )
            anchor = next((p for p in parents if p.tag == "a" and p.get("href")), None)
            home = False
            if anchor is not None:
                target = urljoin(proof["source_url"], anchor.get("href"))
                home = same_site(proof["source_url"], target) and urlsplit(
                    target
                ).path in {"", "/"}
            eligible = eligible or header or home
        if matched and not eligible:
            store["logo_url"] = store["logo_path"] = None
            store["logo_background"] = "light"
            store["missing"]["logo_url"] = "image_not_in_merchant_header_or_home_link"
    store["emails"] = [v for v in store["emails"] if valid_email(v) and v in supported]
    social_values = {}
    for profiles in store["socials"].values():
        for value in profiles:
            clean = social_link(value)
            if clean:
                social_values.setdefault(clean[0], set()).add(clean[1])
    store["socials"] = {k: sorted(v) for k, v in sorted(social_values.items())}
    evidence = []
    for proof in store["evidence"]:
        if proof["field"] == "logo_url" and not store["logo_url"]:
            continue
        if proof["field"] == "emails" and (
            proof["value"] not in store["emails"]
            or proof["rule"] == "contradictory_mailto_omitted"
        ):
            continue
        if proof["field"] == "socials":
            pairs = [social_link(v) for v in proof["value"].values()]
            proof["value"] = {p[0]: p[1] for p in pairs if p}
            if not proof["value"]:
                continue
        if proof["field"] == "shopify" and proof["family"] == "delivery":
            if not runtime_asset(proof["value"]):
                continue
        evidence.append(proof)
    if store["shopify"] == "verified" and not any(
        e["field"] == "shopify" and e["family"] == "delivery" for e in evidence
    ):
        for page in cached_pages:
            tree = cached_tree(page["content_hash"])
            if tree is None:
                continue
            found = None
            for tag in tree.xpath("//script[@src] | //link[@href]"):
                src = tag.get("src") or tag.get("href") or ""
                if runtime_asset(src):
                    found = src
                    break
            if found:
                evidence.append(
                    {
                        "field": "shopify",
                        "value": urljoin(page["final_url"], found),
                        "rule": "shopify_runtime_asset",
                        "excerpt": found[:900],
                        "source_url": page["final_url"],
                        "observed_at": page["observed_at"],
                        "content_hash": page["content_hash"],
                        "family": "delivery",
                    }
                )
                break
        else:
            store["shopify"] = "unconfirmed"
            store["status"] = "review"
            store["reason"] = (
                "No separate Shopify JavaScript or stylesheet asset found in saved pages."
            )
    store["evidence"] = evidence
    for field in ("emails", "socials"):
        if store[field]:
            store["missing"].pop(field, None)
        else:
            store["missing"][field] = "not_found_after_contact_profile_validation"
    store["rule_version"] = RULE_VERSION
    return Store.model_validate(store).model_dump()


def refine_saved(db, source_run_id=None):
    baseline = {}
    if source_run_id:
        with db.connect() as conn:
            run = conn.execute(
                "SELECT * FROM runs WHERE id=?", (source_run_id,)
            ).fetchone()
            if (
                not run
                or run["status"] != "completed"
                or json.loads(run["config"]).get("operation") != "replay"
            ):
                raise ValueError("Choose a completed full replay as the baseline.")
            baseline = {
                row["candidate_id"]: json.loads(row["result_json"])
                for row in conn.execute(
                    "SELECT candidate_id,result_json FROM run_items WHERE run_id=? AND status='done'",
                    (source_run_id,),
                )
            }
    config = CrawlConfig(operation="refine", offline=True)
    settings = {**config.to_dict(), "baseline_run": source_run_id}
    rid, candidates = db.start_run(settings, 10000)
    try:
        for candidate in candidates:
            if db.pause_requested(rid):
                db.finish_run(rid, "cancelled")
                return rid
            db.heartbeat(rid)
            db.item_started(rid, candidate["id"])
            previous = db.latest_page_run(candidate["id"])
            pages = db.cached_pages(previous, candidate["id"]) if previous else []
            source = json.loads(candidate["store_json"])
            if source_run_id:
                earlier = baseline.get(candidate["id"])
                if not earlier or earlier["observed_at"] != source["observed_at"]:
                    raise ValueError(
                        "Baseline does not match the current observations."
                    )
                source = earlier
            store = refine_store(source, pages, db.path.parent / "cache")
            db.save_result(rid, candidate["id"], store)
        db.finish_run(rid, "completed")
    except Exception as exc:
        db.finish_run(rid, "failed", str(exc)[:500])
        raise
    return rid

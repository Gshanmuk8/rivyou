"""Check submission bytes, CSV/JSON parity, uniqueness and field provenance.

These checks find packaging and internal consistency errors. They do not prove
that a merchant's own address is true or replace reading the source pages.
"""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from rivyou.extract import runtime_asset, social_link, valid_email
from rivyou.report import FIELDS, csv_safe


def validate(folder: Path) -> dict:
    errors = []
    manifest = json.loads((folder / "manifest.json").read_bytes())
    for name, expected in manifest["files"].items():
        path = folder / name
        if path.resolve().parent != folder.resolve():
            errors.append(f"Unsafe manifest path: {name}")
            continue
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            errors.append(f"Checksum mismatch: {name}")
    stores = json.loads((folder / "stores.json").read_bytes())
    csv_rows = list(
        csv.DictReader(
            io.StringIO((folder / "stores.csv").read_bytes().decode("utf-8"))
        )
    )
    evidence = [
        json.loads(line)
        for line in (folder / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    by_id = {row["store_id"]: row for row in evidence}
    if (
        len(stores) != len(csv_rows)
        or len(stores) != manifest["records"]
        or len(stores) != len(evidence)
    ):
        errors.append("Row counts differ across the snapshot.")
    for key in ("domain_url", "store_id"):
        if len({s[key] for s in stores}) != len(stores):
            errors.append(f"Duplicate {key} values.")
    identities = [e.get("shop_identity") for e in evidence]
    if len(set(identities)) != len(identities) or None in identities:
        errors.append("Shop identities are missing or duplicated.")
    for index, store in enumerate(stores):
        sid = store["store_id"]
        proof = by_id.get(sid, {})
        if proof.get("shopify") != "verified" or proof.get("india") != "verified":
            errors.append(f"Verification missing: {sid}")
        fields = {item["field"] for item in proof.get("evidence", [])}
        if not {"shopify", "india"}.issubset(fields):
            errors.append(f"Required evidence missing: {sid}")
        families = {
            item.get("family")
            for item in proof.get("evidence", [])
            if item["field"] == "shopify"
        }
        if not {"identity", "delivery", "commerce"}.issubset(families):
            errors.append(f"Incomplete Shopify signal families: {sid}")
        if not proof.get("sources"):
            errors.append(f"Discovery attribution missing: {sid}")
        if any(not valid_email(value) for value in store["emails"]):
            errors.append(f"Invalid or template email: {sid}")
        for network, profiles in store["socials"].items():
            if any(social_link(value) != (network, value) for value in profiles):
                errors.append(f"Invalid or noncanonical social profile: {sid}")
        if not any(
            item["field"] == "shopify"
            and item.get("family") == "delivery"
            and runtime_asset(item["value"])
            for item in proof.get("evidence", [])
        ):
            errors.append(f"Shopify runtime is not JavaScript or CSS: {sid}")
        for field in FIELDS:
            if index < len(csv_rows) and csv_safe(store.get(field)) != csv_rows[
                index
            ].get(field):
                errors.append(f"CSV/JSON mismatch: {sid}/{field}")
            if field != "domain_url" and store.get(field) and field not in fields:
                errors.append(f"Field has no evidence: {sid}/{field}")
        for item in proof.get("evidence", []):
            if (
                not item.get("source_url")
                or len(item.get("content_hash", "")) != 64
                or not item.get("observed_at")
            ):
                errors.append(f"Incomplete provenance: {sid}/{item.get('field')}")
    return {
        "snapshot_id": manifest["snapshot_id"],
        "records": len(stores),
        "passed": not errors,
        "errors": errors,
        "scope": "File integrity and internal consistency; not an independent accuracy audit.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, nargs="?", default=Path("outputs"))
    args = parser.parse_args()
    result = validate(args.folder)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()

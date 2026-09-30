"""Build a static, read-only view of the submitted snapshot for GitHub Pages."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
SITE = ROOT / "site"
DEST = ROOT / "site_dist"
DOWNLOADS = (
    "stores.csv",
    "stores.json",
    "evidence.jsonl",
    "run-report.json",
    "source-manifest.json",
    "unresolved.json",
    "audit-sample.json",
    "manifest.json",
)


def build() -> None:
    manifest = json.loads((OUTPUTS / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected in manifest["files"].items():
        actual = hashlib.sha256((OUTPUTS / filename).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Snapshot checksum mismatch: {filename}")

    stores = json.loads((OUTPUTS / "stores.json").read_text(encoding="utf-8"))
    report = json.loads((OUTPUTS / "run-report.json").read_text(encoding="utf-8"))
    if len(stores) != manifest["records"] or report["accepted"] != len(stores):
        raise ValueError("Store count does not match the published snapshot")
    store_ids = {store["store_id"] for store in stores}
    if len(store_ids) != len(stores):
        raise ValueError("Duplicate store ID in snapshot")

    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(SITE, DEST)
    html = (DEST / "index.html").read_text(encoding="utf-8")
    for name, placeholder in (("app.css", "__CSS_VERSION__"), ("app.js", "__JS_VERSION__")):
        digest = hashlib.sha256((DEST / name).read_bytes()).hexdigest()[:12]
        if placeholder not in html:
            raise ValueError(f"Missing asset version placeholder: {placeholder}")
        html = html.replace(placeholder, digest)
    (DEST / "index.html").write_text(html, encoding="utf-8")
    (DEST / ".nojekyll").touch()
    assets = DEST / "assets"
    assets.mkdir()
    brand = ROOT / "src" / "rivyou" / "static" / "brand"
    shutil.copy2(brand / "rivyou.svg", assets / "rivyou.svg")
    shutil.copy2(ROOT / "src" / "rivyou" / "static" / "favicon.svg", assets / "favicon.svg")
    for name in ("dmsans-0.ttf", "dmsans-1.ttf", "outfit-0.ttf", "outfit-1.ttf"):
        shutil.copy2(brand / name, assets / name)

    data = DEST / "data"
    data.mkdir()
    evidence_dir = data / "evidence"
    evidence_dir.mkdir()
    seen_evidence = set()
    with (OUTPUTS / "evidence.jsonl").open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            store_id = record["store_id"]
            if store_id not in store_ids or store_id in seen_evidence:
                raise ValueError(f"Unexpected or duplicate evidence record: {store_id}")
            seen_evidence.add(store_id)
            (evidence_dir / f"{store_id}.json").write_text(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
    if seen_evidence != store_ids:
        raise ValueError("Evidence missing for accepted stores")

    for filename in DOWNLOADS:
        shutil.copy2(OUTPUTS / filename, data / filename)
    print(f"Built site for {len(stores):,} stores at {DEST}")


if __name__ == "__main__":
    build()

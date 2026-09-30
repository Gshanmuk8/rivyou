from rivyou.sources import parse_leads


def test_exported_sources_import_as_queued_leads_with_all_attribution(db, tmp_path):
    import json

    from rivyou.discovery import import_json

    path = tmp_path / "source-manifest.json"
    path.write_text(
        json.dumps(
            [
                {
                    "candidate_url": "https://merchant.in/",
                    "status": "accepted",
                    "sources": [
                        {
                            "name": "First source",
                            "source_url": "https://example.com/one",
                        },
                        {
                            "name": "Second source",
                            "source_url": "https://example.com/two",
                        },
                    ],
                }
            ]
        )
    )
    result = import_json(db, path)
    assert result["added"] == 1 and not result["errors"]
    row = db.all_candidates()[0]
    assert row["status"] == "queued" and row["store"] is None
    assert {s["name"] for s in row["sources"]} == {"First source", "Second source"}


async def test_cached_source_preserves_date_hash_and_does_not_use_network(
    db, tmp_path, monkeypatch
):
    import json

    from rivyou.cache import write_snapshot
    from rivyou.sources import SOURCES, discover_source

    cache = db.path.parent / "cache"
    cache.mkdir()
    content = b"https://first.in\nhttps://second.in\n"
    import hashlib

    digest = hashlib.sha256(content).hexdigest()
    write_snapshot(cache, content)
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "dukaan-0-1.json").write_text(
        json.dumps(
            {
                "download_url": SOURCES["dukaan"]["url"],
                "content_hash": digest,
                "retrieved_at": "2026-09-29T00:00:00+00:00",
            }
        )
    )

    def reject_network(*args, **kwargs):
        raise AssertionError("Cached discovery must not make network requests")

    monkeypatch.setattr("rivyou.sources.Fetcher", reject_network)
    manifest = await discover_source(db, "dukaan", 1, 1, manifests, cached=True)
    assert manifest["content_hash"] == digest
    assert manifest["retrieved_at"] == "2026-09-29T00:00:00+00:00"
    assert manifest["result"]["added"] == 1
    assert db.all_candidates()[0]["url"] == "https://second.in/"


def test_line_source_normalizes_deduplicates_and_rejects_private_urls():
    assert parse_leads(
        "URL\nhttps://brand.in\nhttps://brand.in/\nhttp://127.0.0.1/\n", "lines"
    ) == ["https://brand.in/"]


def test_directory_only_reads_store_cells_not_other_tables_or_marketing():
    html = """<table><tr><th>Store</th><th>Title</th></tr>
    <tr><td>brand.in Top 5K</td><td>Another site unrelated.com</td></tr></table>
    <table><tr><th>Theme</th></tr><tr><td>ignore.com</td></tr></table>"""
    assert parse_leads(html, "store_tables") == ["https://brand.in/"]

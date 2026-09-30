from scripts.build_dataset import checkpoint


def test_empty_driver_checkpoint_preserves_a_previous_submission(db, tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    path = output / "manifest.json"
    path.write_bytes(b"previous snapshot")
    assert checkpoint(db, output) == 0
    db.import_candidates(
        [
            {
                "url": "https://example.com",
                "source": "Fixture",
                "source_url": "https://example.com/list",
            }
        ]
    )
    assert checkpoint(db, output) == 0
    assert path.read_bytes() == b"previous snapshot"

import hashlib

import pytest

from rivyou.cache import read_snapshot, write_snapshot


def test_compressed_snapshots_round_trip_and_keep_original_content_hash(tmp_path):
    body = b"<p>Merchant address</p>" * 1000
    digest = hashlib.sha256(body).hexdigest()
    path = write_snapshot(tmp_path, body)
    assert path.suffix == ".gz"
    assert path.stat().st_size < len(body) / 10
    assert read_snapshot(tmp_path, digest) == body
    assert write_snapshot(tmp_path, body) == path


def test_old_uncompressed_snapshots_remain_readable_and_corruption_is_reported(
    tmp_path,
):
    body = b"original"
    digest = hashlib.sha256(body).hexdigest()
    (tmp_path / digest).write_bytes(body)
    assert read_snapshot(tmp_path, digest) == body
    (tmp_path / digest).write_bytes(b"altered")
    with pytest.raises(ValueError, match="checksum"):
        read_snapshot(tmp_path, digest)


def test_cache_paths_cannot_escape_the_cache_directory(tmp_path):
    with pytest.raises(ValueError, match="digest"):
        read_snapshot(tmp_path, "../secrets")


def test_empty_response_has_no_snapshot(tmp_path):
    from rivyou.cache import read_snapshot

    assert read_snapshot(tmp_path, "") is None

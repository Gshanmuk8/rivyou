"""Content-addressed snapshots, compressed without changing evidence hashes."""

import gzip
import hashlib
import os
import re
import tempfile
from pathlib import Path


def _path(folder: Path, digest: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid snapshot digest.")
    return folder / digest


def read_snapshot(folder: Path, digest: str) -> bytes | None:
    if not digest:
        return None  # Empty HTTP bodies have no stored snapshot.
    path = _path(folder, digest)
    if path.is_file():
        body = path.read_bytes()  # Backward-compatible with earlier runs.
    elif path.with_suffix(".gz").is_file():
        body = gzip.decompress(path.with_suffix(".gz").read_bytes())
    else:
        return None
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("Cached snapshot failed its content checksum.")
    return body


def write_snapshot(folder: Path, body: bytes) -> Path:
    digest = hashlib.sha256(body).hexdigest()
    path = _path(folder, digest)
    compressed_path = path.with_suffix(".gz")
    if path.exists():
        return path
    if compressed_path.exists():
        return compressed_path
    compressed = gzip.compress(body, compresslevel=3, mtime=0)
    target, content = (
        (compressed_path, compressed) if len(compressed) < len(body) else (path, body)
    )
    # A killed process must not leave a partial file under a valid content hash.
    with tempfile.NamedTemporaryFile(
        dir=folder, prefix=".snapshot-", delete=False
    ) as file:
        temporary = Path(file.name)
        file.write(content)
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target

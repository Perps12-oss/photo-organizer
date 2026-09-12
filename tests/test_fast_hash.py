from __future__ import annotations

from fast_hash import full_hash, hash_many_parallel, quick_hash


def test_identical_files_share_hashes(tmp_path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    payload = b"photo-organizer-hash-fixture" * 200
    a.write_bytes(payload)
    b.write_bytes(payload)
    assert quick_hash(str(a)) == quick_hash(str(b))
    assert full_hash(str(a)) == full_hash(str(b))
    assert quick_hash(str(a))
    assert full_hash(str(a))


def test_different_content_different_full_hash(tmp_path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"AAAA")
    b.write_bytes(b"BBBB")
    assert full_hash(str(a)) != full_hash(str(b))


def test_hash_many_parallel(tmp_path) -> None:
    files = []
    for i in range(4):
        p = tmp_path / f"{i}.bin"
        p.write_bytes(b"x" * (i + 1) * 16)
        files.append(str(p))
    results = hash_many_parallel(files, full_hash, max_workers=2)
    assert set(results) == set(files)

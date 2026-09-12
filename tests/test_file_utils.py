from __future__ import annotations

from file_utils import (
    is_readable_file,
    iter_file_chunks,
    normalize_filepath,
    should_skip_dir,
    unreadable_reason,
)


def test_should_skip_hidden_and_cache_dirs() -> None:
    assert should_skip_dir(".git")
    assert should_skip_dir(".cache")
    assert should_skip_dir(".thumbnails")
    assert not should_skip_dir("Photos")
    assert not should_skip_dir("Vacation 2024")


def test_normalize_filepath_is_absolute(tmp_path) -> None:
    p = tmp_path / "x.txt"
    p.write_text("hi", encoding="utf-8")
    out = normalize_filepath(str(p))
    assert out == str(p.resolve())


def test_readable_file_and_chunks(tmp_path) -> None:
    p = tmp_path / "a.bin"
    payload = b"abcdefgh" * 1000
    p.write_bytes(payload)
    assert unreadable_reason(str(p)) is None
    assert is_readable_file(str(p))
    joined = b"".join(iter_file_chunks(str(p), chunk_size=64))
    assert joined == payload


def test_missing_file_is_unreadable(tmp_path) -> None:
    missing = tmp_path / "nope.bin"
    reason = unreadable_reason(str(missing))
    assert reason is not None
    assert not is_readable_file(str(missing))

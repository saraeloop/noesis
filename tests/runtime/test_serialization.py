from pathlib import Path

import pytest

from noesis.runtime.serialization import atomic_write_json, canonical_dumps


def test_canonical_dumps_orders_keys_and_compacts() -> None:
    payload = {"b": 2, "a": {"z": 1, "y": 0}}
    serialized = canonical_dumps(payload)
    assert serialized == '{"a":{"y":0,"z":1},"b":2}'


def test_atomic_write_json_normalizes_newline(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    atomic_write_json(target, {"b": 2, "a": 1})
    contents = target.read_bytes()
    assert contents.endswith(b"\n")
    # canonical ordering expected
    assert contents.rstrip(b"\n") == b'{"a":1,"b":2}'


def test_atomic_write_json_cleans_temp_file_on_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "out.json"

    def _boom(*_args, **_kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", _boom)

    with pytest.raises(OSError, match="replace failed"):
        atomic_write_json(target, {"a": 1})

    # Failed atomic writes should not leave temp files behind.
    assert list(tmp_path.iterdir()) == []

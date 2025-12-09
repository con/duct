from __future__ import annotations
import json
from pathlib import Path
import pytest
from con_duct.duct_main import SUFFIXES
from con_duct.json_utils import (
    JSONL_SUFFIXES,
    is_info_file,
    is_jsonl_file,
    load_info_file,
    load_usage_file,
)


class TestIsJsonlFile:
    def test_usage_jsonl(self) -> None:
        assert is_jsonl_file(f"prefix_{SUFFIXES['usage']}")

    def test_usage_legacy(self) -> None:
        assert is_jsonl_file(f"prefix_{SUFFIXES['usage_legacy']}")

    def test_generic_jsonl(self) -> None:
        assert is_jsonl_file("anything.jsonl")

    def test_info_json_is_not_jsonl(self) -> None:
        assert not is_jsonl_file(f"prefix_{SUFFIXES['info']}")

    def test_random_json_is_not_jsonl(self) -> None:
        assert not is_jsonl_file("something.json")


class TestIsInfoFile:
    def test_info_file(self) -> None:
        assert is_info_file(f"prefix_{SUFFIXES['info']}")

    def test_usage_is_not_info(self) -> None:
        assert not is_info_file(f"prefix_{SUFFIXES['usage']}")

    def test_random_json_is_not_info(self) -> None:
        assert not is_info_file("something.json")


class TestLoadUsageFile:
    def test_load_usage_file(self, tmp_path: Path) -> None:
        usage_file = tmp_path / SUFFIXES["usage"]
        usage_file.write_text(
            '{"timestamp": "2024-01-01", "totals": {"rss": 100}}\n'
            '{"timestamp": "2024-01-02", "totals": {"rss": 200}}\n'
        )
        data = load_usage_file(str(usage_file))
        assert len(data) == 2
        assert data[0]["totals"]["rss"] == 100
        assert data[1]["totals"]["rss"] == 200

    def test_load_empty_usage_file(self, tmp_path: Path) -> None:
        usage_file = tmp_path / SUFFIXES["usage"]
        usage_file.write_text("")
        data = load_usage_file(str(usage_file))
        assert data == []

    def test_load_usage_file_skips_blank_lines(self, tmp_path: Path) -> None:
        usage_file = tmp_path / SUFFIXES["usage"]
        usage_file.write_text('{"a": 1}\n\n{"b": 2}\n')
        data = load_usage_file(str(usage_file))
        assert len(data) == 2


class TestLoadInfoFile:
    def test_load_info_file(self, tmp_path: Path) -> None:
        info_file = tmp_path / SUFFIXES["info"]
        info_file.write_text('{"command": "sleep 1", "exit_code": 0}')
        data = load_info_file(str(info_file))
        assert data["command"] == "sleep 1"
        assert data["exit_code"] == 0

    def test_load_info_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_info_file(str(tmp_path / "nonexistent.json"))

    def test_load_info_file_invalid_json(self, tmp_path: Path) -> None:
        info_file = tmp_path / SUFFIXES["info"]
        info_file.write_text("not valid json")
        with pytest.raises(json.JSONDecodeError):
            load_info_file(str(info_file))


class TestJsonlSuffixes:
    def test_contains_current_and_legacy(self) -> None:
        assert SUFFIXES["usage"] in JSONL_SUFFIXES
        assert SUFFIXES["usage_legacy"] in JSONL_SUFFIXES

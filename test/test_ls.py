import json
import logging
from typing import Any, Dict
from unittest.mock import mock_open, patch
import pytest
from con_duct.__main__ import SummaryFormatter, __schema_version__
from con_duct.suite.ls import (
    _flatten_dict,
    _restrict_row,
    ensure_compliant_schema,
    load_duct_runs,
    process_run_data,
)


def test_load_duct_runs_sanity() -> None:
    mock_json = json.dumps(
        {"schema_version": "0.2.1", "prefix": "/test/path_", "command": "echo hello"}
    )
    with patch("builtins.open", mock_open(read_data=mock_json)):
        result = load_duct_runs(["/test/path_info.json"])
    assert len(result) == 1
    assert result[0]["prefix"] == "/test/path_"


def test_load_duct_runs_skips_unsupported_schema() -> None:
    mock_json = json.dumps(
        {"schema_version": "0.1.1", "prefix": "/test/path_", "command": "echo hello"}
    )
    with patch("builtins.open", mock_open(read_data=mock_json)):
        result = load_duct_runs(["/test/path_info.json"])
    assert len(result) == 0


def test_load_duct_runs_uses_filenames_not_stored_prefix() -> None:
    mock_json = json.dumps(
        {
            "schema_version": "0.2.1",
            "prefix": "/test/not_anymore_",
            "command": "echo hello",
        }
    )
    with patch("builtins.open", mock_open(read_data=mock_json)):
        result = load_duct_runs(["/actual_filepath_info.json"])
    assert len(result) == 1
    assert result[0]["prefix"] == "/actual_filepath_"


def test_flatten_dict() -> None:
    nested = {"a": {"b": 1, "c": 2}, "d": 3}
    result = _flatten_dict(nested)
    assert result == {"b": 1, "c": 2, "d": 3}


def test_restrict_row() -> None:
    row = {"prefix": "/test/path", "exit_code": 0, "extra": "ignore"}
    fields = ["exit_code"]
    result = _restrict_row(fields, row)
    assert "prefix" in result
    assert "exit_code" in result
    assert "extra" not in result


def test_process_run_data() -> None:
    run_data = [
        {
            "prefix": "/test/path",
            "exit_code": 0,
            "wall_clock_time": 0.12345678,
        }
    ]
    formatter = SummaryFormatter(enable_colors=False)
    result = process_run_data(run_data, ["wall_clock_time"], formatter)
    assert isinstance(result, list)
    assert result[0]["prefix"] == "/test/path"
    assert "exit_code" not in result[0]
    assert result[0]["wall_clock_time"] == "0.123 sec"


def test_ensure_compliant_schema_noop_for_current_version() -> None:
    info: Dict[str, Any] = {
        "schema_version": __schema_version__,
        "execution_summary": {},
    }
    ensure_compliant_schema(info)
    assert "working_directory" not in info["execution_summary"]


def test_ensure_compliant_schema_adds_field_for_old_version() -> None:
    info: Dict[str, Any] = {"schema_version": "0.2.0", "execution_summary": {}}
    ensure_compliant_schema(info)
    assert info["execution_summary"]["working_directory"] == ""
    assert info["message"] == ""


def test_ensure_compliant_schema_ignores_unexpected_future_version() -> None:
    info: Dict[str, Any] = {"schema_version": "99.0.0", "execution_summary": {}}
    ensure_compliant_schema(info)
    assert "working_directory" not in info["execution_summary"]


def test_load_duct_runs_handles_empty_json_files(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test desired behavior: empty JSON files produce debug logs and are skipped."""
    with patch("builtins.open", mock_open(read_data="")):
        with caplog.at_level(logging.DEBUG):
            result = load_duct_runs(["/test/empty_info.json"])

    # empty files result in empty list
    assert len(result) == 0
    # empty files result in debug level log (not warning)
    assert len([r for r in caplog.records if r.levelname == "DEBUG"]) == 1
    assert not any(r for r in caplog.records if r.levelname == "WARNING")
    assert "Skipping empty file" in caplog.text


def test_load_duct_runs_handles_invalid_json_files(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test current behavior: invalid JSON files produce warnings and are skipped."""
    with patch("builtins.open", mock_open(read_data="not json at all")):
        with caplog.at_level(logging.WARNING):
            result = load_duct_runs(["/test/invalid_info.json"])

    assert len(result) == 0
    assert len(caplog.records) == 1
    assert "Failed to load file" in caplog.text


def test_load_duct_runs_mixed_empty_and_valid_files(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test behavior with mix of empty and valid JSON files."""
    valid_json = json.dumps(
        {"schema_version": "0.2.1", "prefix": "/test/path_", "command": "echo hello"}
    )

    def side_effect(filename: str) -> Any:
        if "empty" in filename:
            return mock_open(read_data="")()
        else:
            return mock_open(read_data=valid_json)()

    with patch("builtins.open", side_effect=side_effect):
        with caplog.at_level(logging.DEBUG):
            result = load_duct_runs(["/test/empty_info.json", "/test/valid_info.json"])

    # only valid file is loaded
    assert len(result) == 1
    assert result[0]["prefix"] == "/test/valid_"
    # debug log for empty file, no warning
    assert len([r for r in caplog.records if r.levelname == "DEBUG"]) == 1
    assert not any(r for r in caplog.records if r.levelname == "WARNING")
    assert "Skipping empty file" in caplog.text

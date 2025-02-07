import json
from unittest.mock import mock_open, patch
from con_duct.__main__ import SummaryFormatter
from con_duct.suite.ls import (
    _flatten_dict,
    _restrict_row,
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

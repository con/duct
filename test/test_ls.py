import argparse
import contextlib
from io import StringIO
import json
import logging
import os
import tempfile
from typing import Any, Dict, Optional
import unittest
from unittest.mock import mock_open, patch
import pytest
from con_duct.duct_main import SummaryFormatter, __schema_version__
from con_duct.ls import (
    MINIMUM_SCHEMA_VERSION,
    _flatten_dict,
    _restrict_row,
    ensure_compliant_schema,
    load_duct_runs,
    ls,
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


class TestLS(unittest.TestCase):
    def setUp(self) -> None:
        """Create a temporary directory and test files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        self.files = {
            "file1_info.json": {
                "schema_version": MINIMUM_SCHEMA_VERSION,
                "execution_summary": {},
                "prefix": "test1",
                "filter_this": "yes",
            },
            "file2_info.json": {
                "schema_version": MINIMUM_SCHEMA_VERSION,
                "execution_summary": {},
                "prefix": "test2",
                "filter_this": "no",
            },
            "file3_info.json": {
                "schema_version": "0.1.0",
                "execution_summary": {},
                "prefix": "old_version",
            },
            "not_matching.json": {
                "schema_version": MINIMUM_SCHEMA_VERSION,
                "execution_summary": {},
                "prefix": "no_match",
            },
            ".duct/logs/default_logpath_info.json": {
                "schema_version": MINIMUM_SCHEMA_VERSION,
                "execution_summary": {},
                "prefix": "default_file1",
            },
        }
        for filename, content in self.files.items():
            full_path = os.path.join(self.temp_dir.name, filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                json.dump(content, f)

    def tearDown(self) -> None:
        """Clean up the temporary directory."""
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()

    def _run_ls(
        self, paths: list[str], fmt: str, args: Optional[argparse.Namespace] = None
    ) -> str:
        """Helper function to run ls() and capture stdout."""
        if args is None:
            args = argparse.Namespace(
                paths=[os.path.join(self.temp_dir.name, path) for path in paths],
                colors=False,
                fields=["prefix", "schema_version"],
                eval_filter=None,
                format=fmt,
                func=ls,
                reverse=False,
            )
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = ls(args)
            assert exit_code == 0
        return buf.getvalue().strip()

    def test_ls_sanity(self) -> None:
        """Basic sanity test to ensure ls() runs without crashing."""
        just_file1 = ["file1_info.json"]
        result = self._run_ls(just_file1, "summaries")

        assert "Prefix:" in result
        prefixes = [
            line.split(":", 1)[1].strip()
            for line in result.splitlines()
            if line.startswith("Prefix:")
        ]
        assert len(prefixes) == 1
        assert any("file1" in p for p in prefixes)

    def test_ls_with_filter(self) -> None:
        """Basic sanity test to ensure ls() runs without crashing."""
        paths = ["file1_info.json", "file2_info.json"]
        args = argparse.Namespace(
            paths=[os.path.join(self.temp_dir.name, path) for path in paths],
            colors=False,
            fields=["prefix", "schema_version"],
            eval_filter="filter_this=='yes'",
            format="summaries",
            func=ls,
            reverse=False,
        )
        result = self._run_ls(paths, "summaries", args)

        assert "Prefix:" in result
        prefixes = [
            line.split(":", 1)[1].strip()
            for line in result.splitlines()
            if line.startswith("Prefix:")
        ]
        assert len(prefixes) == 1
        assert any("file1" in p for p in prefixes)
        # filter_this == 'no'
        assert "file2" not in result

    def test_ls_no_pos_args(self) -> None:
        result = self._run_ls([], "summaries")

        assert "Prefix:" in result
        prefixes = [
            line.split(":", 1)[1].strip()
            for line in result.splitlines()
            if line.startswith("Prefix:")
        ]
        assert len(prefixes) == 1
        assert any("default_logpath" in p for p in prefixes)

        assert "file1" not in result
        assert "file2" not in result
        assert "file3" not in result
        assert "not_matching.json" not in result

    def test_ls_multiple_paths(self) -> None:
        """Basic sanity test to ensure ls() runs without crashing."""
        files_1_and_2 = ["file1_info.json", "file2_info.json"]
        result = self._run_ls(files_1_and_2, "summaries")

        assert "Prefix:" in result
        prefixes = [
            line.split(":", 1)[1].strip()
            for line in result.splitlines()
            if line.startswith("Prefix:")
        ]
        assert len(prefixes) == 2
        assert any("file1" in p for p in prefixes)
        assert any("file2" in p for p in prefixes)

    def test_ls_ignore_old_schema(self) -> None:
        """Basic sanity test to ensure ls() runs without crashing."""
        files_1_2_3 = ["file1_info.json", "file2_info.json", "file3_info.json"]
        result = self._run_ls(files_1_2_3, "summaries")

        assert "Prefix:" in result
        prefixes = [
            line.split(":", 1)[1].strip()
            for line in result.splitlines()
            if line.startswith("Prefix:")
        ]
        assert len(prefixes) == 2
        assert any("file1" in p for p in prefixes)
        assert any("file2" in p for p in prefixes)
        # file3 does not meet minimum schema version
        assert "file3" not in result

    def test_ls_ignore_non_infojson(self) -> None:
        """Basic sanity test to ensure ls() runs without crashing."""
        all_files = ["file1_info.json", "file2_info.json", "not_matching.json"]
        result = self._run_ls(all_files, "summaries")

        assert "Prefix:" in result
        prefixes = [
            line.split(":", 1)[1].strip()
            for line in result.splitlines()
            if line.startswith("Prefix:")
        ]
        assert len(prefixes) == 2
        assert any("file1" in p for p in prefixes)
        assert any("file2" in p for p in prefixes)
        # does not end in info.json
        assert "not_matching.json" not in result

    def test_ls_json_output(self) -> None:
        """Test JSON output format."""
        result = self._run_ls(["file1_info.json"], "json")
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert "prefix" in parsed[0]

    def test_ls_json_pp_output(self) -> None:
        """Test pretty-printed JSON output format."""
        result = self._run_ls(["file1_info.json"], "json_pp")
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert "prefix" in parsed[0]

    def test_ls_yaml_output(self) -> None:
        """Test YAML output format."""
        yaml = pytest.importorskip("yaml")
        result = self._run_ls(["file1_info.json"], "yaml")
        parsed = yaml.safe_load(result)
        assert len(parsed) == 1
        assert "prefix" in parsed[0]

    def test_ls_pyout_output(self) -> None:
        """Test pyout output format."""
        pytest.importorskip("pyout")
        result = self._run_ls(["file1_info.json"], "pyout")
        # pyout header
        assert "PREFIX" in result
        assert os.path.join(self.temp_dir.name, "file1_") in result

    def test_ls_reverse(self) -> None:
        """Test --reverse flag lists entries in reverse order."""
        paths = ["file1_info.json", "file2_info.json"]

        # Get normal order
        result_normal = self._run_ls(paths, "json")
        parsed_normal = json.loads(result_normal)
        prefixes_normal = [row["prefix"] for row in parsed_normal]

        # Get reversed order
        args = argparse.Namespace(
            paths=[os.path.join(self.temp_dir.name, path) for path in paths],
            colors=False,
            fields=["prefix", "schema_version"],
            eval_filter=None,
            format="json",
            func=ls,
            reverse=True,
        )
        result_reversed = self._run_ls(paths, "json", args)
        parsed_reversed = json.loads(result_reversed)
        prefixes_reversed = [row["prefix"] for row in parsed_reversed]

        assert prefixes_reversed == list(reversed(prefixes_normal))

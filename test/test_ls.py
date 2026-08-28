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
from con_duct._constants import __schema_version__
from con_duct._formatter import SummaryFormatter
from con_duct.ls import (
    LS_FIELD_CHOICES,
    MINIMUM_SCHEMA_VERSION,
    VALUE_TRANSFORMATION_MAP,
    _flatten_dict,
    _natural_chunks,
    _restrict_row,
    _sort_key,
    compile_eval_filter,
    ensure_compliant_schema,
    load_duct_runs,
    ls,
    process_run_data,
)


def test_load_duct_runs_sanity() -> None:
    mock_json = json.dumps(
        {
            "schema_version": "0.2.1",
            "prefix": "/test/path_",
            "command": "echo hello",
            "system": {},
        }
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
            "system": {},
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
    info: Dict[str, Any] = {
        "schema_version": "0.2.0",
        "execution_summary": {},
        "system": {},
    }
    ensure_compliant_schema(info)
    assert info["execution_summary"]["working_directory"] == ""
    assert info["message"] == ""
    for field in (
        "os_name",
        "os_release",
        "os_version",
        "arch",
        "processor",
        "distro_id",
        "distro_id_like",
        "distro_name",
        "distro_version",
        "distro_version_id",
        "distro_codename",
        "distro_variant_id",
        "distro_pretty_name",
        "distro_build_id",
    ):
        assert info["system"][field] == ""


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
        {
            "schema_version": "0.2.1",
            "prefix": "/test/path_",
            "command": "echo hello",
            "system": {},
        }
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


def test_compile_eval_filter_none_returns_none() -> None:
    assert compile_eval_filter(None) is None


def test_compile_eval_filter_valid() -> None:
    code = compile_eval_filter("exit_code == 0")
    assert code is not None
    assert eval(code, {"exit_code": 0}) is True
    assert eval(code, {"exit_code": 1}) is False


def test_compile_eval_filter_rejects_nbsp() -> None:
    """Regression test for gh-440: a U+00A0 in the filter must fail
    up-front with a clear message that mentions the character, rather
    than surfacing later as per-file "Failed to load file" warnings."""
    # Note the U+00A0 non-breaking space between "and" and "exit_code",
    # exactly as reported by a macOS user in gh-440 (Option+Space).
    bad_expr = '"fmriprep" in command and\u00a0exit_code == 1'
    with pytest.raises(ValueError, match="U\\+00A0"):
        compile_eval_filter(bad_expr)


def test_compile_eval_filter_rejects_syntax_error() -> None:
    with pytest.raises(ValueError, match="Invalid --eval-filter"):
        compile_eval_filter("this is not valid python")


def test_ls_exits_cleanly_on_bad_filter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`con-duct ls` should error out with a clear message and non-zero
    exit code when --eval-filter has a syntax error, without traceback --
    and before any file is opened, so the failure is never misattributed
    to a log file as a "Failed to load" warning."""
    args = argparse.Namespace(
        paths=["/no/such/file_info.json", "/no/such/other_info.json"],
        colors=False,
        fields=["prefix"],
        eval_filter='"x" in command and\u00a0exit_code == 1',
        format="summaries",
        func=ls,
        reverse=False,
        sort_by=None,
    )
    with caplog.at_level(logging.ERROR):
        with patch("builtins.open") as mock_open_fn:
            rc = ls(args)
    assert rc == 2
    mock_open_fn.assert_not_called()
    assert any("U+00A0" in r.message for r in caplog.records)
    assert not any("Failed to load file" in r.message for r in caplog.records)


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
                "system": {},
                "prefix": "test1",
                "filter_this": "yes",
            },
            "file2_info.json": {
                "schema_version": MINIMUM_SCHEMA_VERSION,
                "execution_summary": {},
                "system": {},
                "prefix": "test2",
                "filter_this": "no",
            },
            "file3_info.json": {
                "schema_version": "0.1.0",
                "execution_summary": {},
                "system": {},
                "prefix": "old_version",
            },
            "not_matching.json": {
                "schema_version": MINIMUM_SCHEMA_VERSION,
                "execution_summary": {},
                "system": {},
                "prefix": "no_match",
            },
            ".duct/logs/default_logpath_info.json": {
                "schema_version": MINIMUM_SCHEMA_VERSION,
                "execution_summary": {},
                "system": {},
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
                sort_by=None,
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
            sort_by=None,
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
            sort_by=None,
        )
        result_reversed = self._run_ls(paths, "json", args)
        parsed_reversed = json.loads(result_reversed)
        prefixes_reversed = [row["prefix"] for row in parsed_reversed]

        assert prefixes_reversed == list(reversed(prefixes_normal))


def _write_run(path: Any, **fields: Any) -> str:
    """Write a minimal info.json containing `fields` and return its path.

    Args:
        path: Destination `*_info.json` path.
        fields: Extra top level fields to store in the record.  The current
            schema version is used by default so that
            `ensure_compliant_schema` does not overwrite them.

    Returns:
        The path written, as a string.
    """
    record: Dict[str, Any] = {
        "schema_version": __schema_version__,
        "execution_summary": {},
        # present so that ensure_compliant_schema() can backfill into it
        # whenever a test writes an older schema_version
        "system": {},
    }
    record.update(fields)
    path.write_text(json.dumps(record))
    return str(path)


def _ls_prefixes(
    paths: list[str],
    sort_by: Optional[list[str]] = None,
    reverse: bool = False,
    fields: Optional[list[str]] = None,
) -> list[str]:
    """Run `ls` in json format and return the prefixes in output order."""
    args = argparse.Namespace(
        paths=paths,
        colors=False,
        fields=fields if fields is not None else ["prefix"],
        eval_filter=None,
        format="json",
        func=ls,
        reverse=reverse,
        sort_by=sort_by,
    )
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        assert ls(args) == 0
    return [row["prefix"] for row in json.loads(buf.getvalue().strip())]


def _basenames(prefixes: list[str]) -> list[str]:
    """Reduce full prefixes to their `runX_` basenames for easy comparison."""
    return [os.path.basename(prefix) for prefix in prefixes]


@pytest.mark.parametrize("reverse", [False, True])
def test_ls_sort_by(reverse: bool, tmp_path: Any) -> None:
    """--sort-by orders entries by the given field; --reverse flips that order."""
    # Deliberately created (and passed) in non sorted order so that the test
    # cannot pass just because the paths happen to be listed sorted already.
    paths = [
        _write_run(tmp_path / name)
        for name in ("run_b_info.json", "run_c_info.json", "run_a_info.json")
    ]
    expected = ["run_a_", "run_b_", "run_c_"]
    if reverse:
        expected = list(reversed(expected))

    assert _basenames(_ls_prefixes(paths, ["prefix"], reverse=reverse)) == expected


def test_ls_sort_by_none_preserves_input_order(tmp_path: Any) -> None:
    """Without --sort-by the order of the given paths is preserved."""
    paths = [
        _write_run(tmp_path / name)
        for name in ("run_b_info.json", "run_c_info.json", "run_a_info.json")
    ]

    assert _basenames(_ls_prefixes(paths)) == ["run_b_", "run_c_", "run_a_"]


def test_ls_sort_by_non_displayed_field(tmp_path: Any) -> None:
    """--sort-by works for fields which are not in --fields (not displayed)."""
    # commands in non-alphabetical order, and paths not sorted by command either
    paths = [
        _write_run(tmp_path / f"run_{letter}_info.json", command=f"cmd_{letter}")
        for letter in ("b", "a", "c")
    ]

    # "command" is intentionally NOT among the displayed fields
    prefixes = _ls_prefixes(paths, ["command"], fields=["prefix"])

    assert _basenames(prefixes) == ["run_a_", "run_b_", "run_c_"]


def test_ls_sort_by_numeric_field_is_not_lexical(tmp_path: Any) -> None:
    """Numeric fields sort numerically, not as their rendered strings.

    Sorting happens on the raw values, so 9 sorts before 10 even though the
    formatted values ("10.000 sec" vs "9.000 sec") would sort the other way.
    """
    paths = [
        _write_run(
            tmp_path / f"run_{i}_info.json",
            execution_summary={"wall_clock_time": wall_clock_time},
        )
        for i, wall_clock_time in enumerate([10.0, 100.0, 9.0])
    ]

    prefixes = _ls_prefixes(
        paths, ["wall_clock_time"], fields=["prefix", "wall_clock_time"]
    )

    assert _basenames(prefixes) == ["run_2_", "run_0_", "run_1_"]


def test_ls_sort_by_version_is_natural(tmp_path: Any) -> None:
    """Version-like strings sort by their numeric components, not lexically."""
    paths = [
        _write_run(tmp_path / f"run_{i}_info.json", schema_version=schema_version)
        for i, schema_version in enumerate(["0.10.0", "0.2.0", "0.9.0"])
    ]

    prefixes = _ls_prefixes(paths, ["schema_version"])

    # lexically "0.10.0" < "0.2.0" < "0.9.0", naturally 0.2.0 < 0.9.0 < 0.10.0
    assert _basenames(prefixes) == ["run_1_", "run_2_", "run_0_"]


def test_ls_sort_by_multiple_fields(tmp_path: Any) -> None:
    """Later --sort-by fields break ties of the earlier ones."""
    runs = [
        ("run_0_info.json", "b", 2.0),
        ("run_1_info.json", "a", 2.0),
        ("run_2_info.json", "a", 1.0),
    ]
    paths = [
        _write_run(
            tmp_path / name,
            command=command,
            execution_summary={"wall_clock_time": wall_clock_time},
        )
        for name, command, wall_clock_time in runs
    ]

    prefixes = _ls_prefixes(paths, ["command", "wall_clock_time"])

    assert _basenames(prefixes) == ["run_2_", "run_1_", "run_0_"]


def test_ls_sort_by_mixed_types_and_missing_values(tmp_path: Any) -> None:
    """Heterogeneous values must not raise, and missing ones sort last.

    info.json files accumulate across duct versions, so a single field can
    hold a number in one run, a string in another, a list in a third and be
    absent from a fourth.
    """
    paths = [
        _write_run(tmp_path / "run_0_info.json", message="text"),
        _write_run(tmp_path / "run_1_info.json"),  # no message at all
        _write_run(tmp_path / "run_2_info.json", message=["a", "list"]),
        _write_run(tmp_path / "run_3_info.json", message=1),
        _write_run(tmp_path / "run_4_info.json", message=None),
        _write_run(tmp_path / "run_5_info.json", message=""),
    ]

    prefixes = _ls_prefixes(paths, ["message"], fields=["prefix", "message"])

    # numbers, then text, then other (json serialized), then the valueless
    # ones -- among which prefix breaks the tie
    assert _basenames(prefixes) == [
        "run_3_",
        "run_0_",
        "run_2_",
        "run_1_",
        "run_4_",
        "run_5_",
    ]


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({}, id="absent"),
        # "gpu" is written as null whenever the machine has no GPU
        pytest.param({"gpu": None}, id="null"),
        # ensure_compliant_schema() backfills newer fields with ""
        pytest.param({"gpu": ""}, id="empty"),
    ],
)
def test_ls_sort_by_valueless_field_warns(
    fields: Dict[str, Any], tmp_path: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """A field no run has a value for warns and does not affect the order.

    A field absent from every record, null in every record, and backfilled
    with "" in every record are all no-ops for ordering, and all are worth
    telling the user about.  Ordering then falls through to the prefix
    tiebreaker rather than to the arbitrary order of the given paths.
    """
    paths = [
        _write_run(tmp_path / name, **fields)
        for name in ("run_b_info.json", "run_a_info.json")
    ]

    with caplog.at_level(logging.WARNING, logger="con_duct.ls"):
        prefixes = _ls_prefixes(paths, ["gpu"])

    assert _basenames(prefixes) == ["run_a_", "run_b_"]
    assert any(
        "No run has a value" in record.message and "gpu" in record.message
        for record in caplog.records
    )


@pytest.mark.parametrize("sort_field", LS_FIELD_CHOICES)
def test_ls_sort_by_each_field(sort_field: str, tmp_path: Any) -> None:
    """Every field in LS_FIELD_CHOICES must sort without crashing."""
    # Values are assigned to run_0/run_1/run_2 in this order and chosen so
    # that the expected sorted order is always run_1 < run_0 < run_2.
    if sort_field == "prefix":
        # prefix comes from the file path, not from the file content
        names = ["run_b_info.json", "run_a_info.json", "run_c_info.json"]
        paths = [_write_run(tmp_path / name) for name in names]
        expected = ["run_a_", "run_b_", "run_c_"]
    else:
        values: list[Any]
        if sort_field in VALUE_TRANSFORMATION_MAP:
            # all transformed fields are numeric -- 10 also proves that they
            # are not compared as strings ("10" would sort before "2")
            values = [2, 1, 10]
        elif sort_field == "schema_version":
            # has to remain a valid version >= MINIMUM_SCHEMA_VERSION
            values = ["0.2.1", "0.2.0", "0.2.2"]
        elif sort_field == "gpu":
            # gpu is a list[dict] -- not orderable without normalization
            values = [[{"name": "gpu_b"}], [{"name": "gpu_a"}], [{"name": "gpu_c"}]]
        else:
            values = ["sort_b", "sort_a", "sort_c"]
        paths = [
            _write_run(tmp_path / f"run_{i}_info.json", **{sort_field: value})
            for i, value in enumerate(values)
        ]
        expected = ["run_1_", "run_0_", "run_2_"]

    prefixes = _ls_prefixes(paths, [sort_field], fields=["prefix", sort_field])

    assert _basenames(prefixes) == expected, f"sort_by={sort_field!r}"


@pytest.mark.parametrize(
    "values,expected",
    [
        # numbers numerically, including bools and negatives
        ([3, 1.5, -2, True], [-2, True, 1.5, 3]),
        # digit runs within text compared as numbers
        (["run10", "run9", "run2"], ["run2", "run9", "run10"]),
        (["0.10.0", "0.9.0", "0.2.0"], ["0.2.0", "0.9.0", "0.10.0"]),
        # numbers before text before other before missing
        (["b", None, 1, ["a"]], [1, "b", ["a"], None]),
    ],
)
def test_sort_key_orders_values(values: list[Any], expected: list[Any]) -> None:
    assert sorted(values, key=_sort_key) == expected


def test_sort_key_handles_non_serializable_values() -> None:
    """Values json cannot serialize fall back to their string form."""
    assert _sort_key(object())[0] == _sort_key([1])[0]


def test_natural_chunks_does_not_choke_on_unicode_digits() -> None:
    """Non-ASCII "digits" which int() cannot parse stay text chunks."""
    # "\u00b2" (superscript two) is str.isdigit() but not matched by ``\d``
    assert _natural_chunks("x\u00b2") == ((1, 0, "x\u00b2"),)


def test_ls_sort_by_long_digit_run(tmp_path: Any) -> None:
    """A digit run too long for int() must not blow up the sort.

    Free-form fields hold whatever the user typed, and int() refuses to
    parse more than sys.get_int_max_str_digits() (4300 by default).
    """
    paths = [
        _write_run(tmp_path / "run_0_info.json", message="9" * 5000),
        _write_run(tmp_path / "run_1_info.json", message="abc"),
        _write_run(tmp_path / "run_2_info.json", message="42"),
    ]

    prefixes = _ls_prefixes(paths, ["message"], fields=["prefix", "message"])

    # 42 is a real number so it sorts first; the oversized run degrades to
    # text and orders against "abc" as text does
    assert _basenames(prefixes) == ["run_2_", "run_0_", "run_1_"]


def test_ls_sort_by_ties_are_deterministic(tmp_path: Any) -> None:
    """Runs whose sort field ties come out in prefix order, not input order.

    Without an explicit sort the paths are whatever `glob` returned, which
    is arbitrary, so equal-keyed runs must not inherit that order.
    """
    names = ["run_a_info.json", "run_m_info.json", "run_z_info.json"]
    paths = [_write_run(tmp_path / name, exit_code=0) for name in names]
    expected = ["run_a_", "run_m_", "run_z_"]

    assert _basenames(_ls_prefixes(paths, ["exit_code"])) == expected
    assert _basenames(_ls_prefixes(list(reversed(paths)), ["exit_code"])) == expected


def test_ls_sort_by_numeric_non_transformed_field(tmp_path: Any) -> None:
    """Numeric fields which are displayed as-is also sort numerically."""
    paths = [
        _write_run(tmp_path / f"run_{i}_info.json", num_samples=num_samples)
        for i, num_samples in enumerate([9, 100, 10])
    ]

    prefixes = _ls_prefixes(paths, ["num_samples"], fields=["prefix", "num_samples"])

    assert _basenames(prefixes) == ["run_0_", "run_2_", "run_1_"]


def test_ls_sort_by_applies_after_eval_filter(tmp_path: Any) -> None:
    """--sort-by orders whatever --eval-filter kept."""
    paths = [
        _write_run(tmp_path / f"run_{letter}_info.json", command=f"cmd_{letter}")
        for letter in ("b", "a", "c")
    ]
    args = argparse.Namespace(
        paths=paths,
        colors=False,
        fields=["prefix", "command"],
        eval_filter="command != 'cmd_b'",
        format="json",
        func=ls,
        reverse=False,
        sort_by=["command"],
    )
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        assert ls(args) == 0

    rows = json.loads(buf.getvalue().strip())
    assert [row["command"] for row in rows] == ["cmd_a", "cmd_c"]


def test_sort_key_treats_nan_as_valueless() -> None:
    """NaN compares false against everything -- it must not decide order."""
    assert sorted([3.0, float("nan"), 1.0, 2.0], key=_sort_key)[:3] == [1.0, 2.0, 3.0]


@pytest.mark.parametrize("value", [None, ""])
def test_sort_key_ranks_valueless_last(value: Any) -> None:
    assert sorted([value, 1, "a"], key=_sort_key) == [1, "a", value]


def test_natural_chunks_keeps_oversized_digit_runs_as_text() -> None:
    digits = "9" * (10**4)
    assert _natural_chunks(digits) == ((1, 0, digits),)

import argparse
import contextlib
from io import StringIO
import json
import os
import tempfile
from typing import Any, Optional
import unittest
from unittest.mock import MagicMock, mock_open, patch
import pytest
import yaml
from con_duct.__main__ import SummaryFormatter
from con_duct.suite import main, plot, pprint_json
from con_duct.suite.ls import MINIMUM_SCHEMA_VERSION, ls


class TestSuiteHelpers(unittest.TestCase):

    def test_execute_returns_int(self) -> None:
        def return_non_int(*_args: Any) -> str:
            return "NOPE"

        args = argparse.Namespace(
            command="invalid",
            file_path="dummy.json",
            func=return_non_int,
            log_level="NONE",
        )
        with pytest.raises(TypeError):
            main.execute(args)

    @patch("con_duct.suite.main.argparse.ArgumentParser")
    def test_parser_mock_sanity(self, mock_parser: MagicMock) -> None:
        mock_args = MagicMock
        mock_args.command = None
        mock_parser.parse_args.return_value = mock_args
        argv = ["/path/to/con-duct", "plot", "--help"]
        main.main(argv)
        mock_parser.return_value.print_help.assert_called_once()

    @patch("con_duct.suite.main.sys.exit", new_callable=MagicMock)
    @patch("con_duct.suite.main.sys.stderr", new_callable=MagicMock)
    @patch("con_duct.suite.main.sys.stdout", new_callable=MagicMock)
    def test_parser_sanity_green(
        self, mock_stdout: MagicMock, mock_stderr: MagicMock, mock_exit: MagicMock
    ) -> None:
        argv = ["--help"]
        main.main(argv)
        # [0][1][0]: [first call][positional args set(0 is self)][first positional]
        out = mock_stdout.write.mock_calls[0][1][0]
        assert "usage: con-duct <command> [options]" in out
        mock_stderr.write.assert_not_called()
        mock_exit.assert_called_once_with(0)

    @patch("con_duct.suite.main.sys.exit", new_callable=MagicMock)
    @patch("con_duct.suite.main.sys.stderr", new_callable=MagicMock)
    @patch("con_duct.suite.main.sys.stdout", new_callable=MagicMock)
    def test_parser_sanity_red(
        self, mock_stdout: MagicMock, mock_stderr: MagicMock, mock_exit: MagicMock
    ) -> None:
        argv = ["--fakehelp"]
        main.main(argv)
        # [0][1][0]: [first call][positional args set(0 is self)][first positional]
        out = mock_stdout.write.mock_calls[0][1][0]
        assert "usage: con-duct <command> [options]" in out
        mock_stderr.write.ssert_not_called()
        # First call
        assert (
            "usage: con-duct <command> [options]"
            in mock_stderr.write.mock_calls[0][1][0]
        )
        # second call
        assert "--fakehelp" in mock_stderr.write.mock_calls[1][1][0]
        mock_exit.assert_called_once_with(2)


class TestPPrint(unittest.TestCase):

    @patch(
        "builtins.open", new_callable=mock_open, read_data='{"mock_key": "mock_value"}'
    )
    @patch("con_duct.suite.pprint_json.pprint")
    def test_pprint_json(self, mock_pprint: MagicMock, mock_open: MagicMock) -> None:
        args = argparse.Namespace(
            command="pp",
            file_path="dummy.json",
            func=pprint_json.pprint_json,
            log_level="NONE",
            humanize=False,
        )
        assert main.execute(args) == 0

        mock_open.assert_called_with("dummy.json", "r")
        mock_pprint.assert_called_once_with({"mock_key": "mock_value"})

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_file_not_found(self, _mock_open: MagicMock) -> None:
        args = argparse.Namespace(
            command="pp",
            file_path="dummy.json",
            func=pprint_json.pprint_json,
            log_level="NONE",
            humanize=False,
        )
        assert main.execute(args) == 1

    @patch("builtins.open", new_callable=mock_open, read_data='{"invalid": "json"')
    @patch("con_duct.suite.pprint_json.pprint")
    def test_pprint_invalid_json(
        self, mock_pprint: MagicMock, mock_open: MagicMock
    ) -> None:
        args = argparse.Namespace(
            command="pp",
            file_path="dummy.json",
            func=pprint_json.pprint_json,
            log_level="NONE",
            humanize=False,
        )
        assert main.execute(args) == 1

        mock_open.assert_called_with("dummy.json", "r")
        mock_pprint.assert_not_called()


class TestPPrintHumanization(unittest.TestCase):
    """Test humanization functionality in pprint_json module"""

    def test_apply_conversion_with_numbers(self) -> None:
        """Test _apply_conversion with numeric values"""

        formatter = SummaryFormatter()
        field_mapping = pprint_json.get_field_conversion_mapping()

        result = pprint_json._apply_conversion(
            "average_pcpu", 85.567, field_mapping, formatter
        )
        assert result == "85.57%"

        result = pprint_json._apply_conversion(
            "peak_rss", 1024000, field_mapping, formatter
        )
        assert result == "1.0 MB"

        result = pprint_json._apply_conversion(
            "wall_clock_time", 3661.5, field_mapping, formatter
        )
        assert result == "1h 1m 1.5s"

        result = pprint_json._apply_conversion(
            "start_time", 1625400000, field_mapping, formatter
        )
        assert "Jul" in result and "2021" in result

    def test_apply_conversion_with_non_numbers(self) -> None:
        """Test _apply_conversion with non-numeric values"""

        formatter = SummaryFormatter()
        field_mapping = pprint_json.get_field_conversion_mapping()

        # Test string values (should be returned unchanged)
        result = pprint_json._apply_conversion(
            "average_pcpu", "unknown", field_mapping, formatter
        )
        assert result == "unknown"

        # Test None values (should be returned unchanged)
        result = pprint_json._apply_conversion(
            "average_pcpu", None, field_mapping, formatter
        )
        assert result is None

    def test_apply_conversion_unmapped_fields(self) -> None:
        """Test _apply_conversion with unmapped field names"""

        formatter = SummaryFormatter()
        field_mapping = pprint_json.get_field_conversion_mapping()

        # Test unmapped field (should be returned unchanged)
        result = pprint_json._apply_conversion(
            "unknown_field", 42.0, field_mapping, formatter
        )
        assert result == 42.0

        # Test unmapped field (should be returned unchanged)
        result = pprint_json._apply_conversion(
            "unknown_field", "some_string", field_mapping, formatter
        )
        assert result == "some_string"

    def test_humanize_data_simple_dict(self) -> None:
        """Test humanize_data with a simple dictionary"""

        data = {
            "average_pcpu": 85.567,
            "average_rss": 1024000,
            "wall_clock_time": 150.75,
            "unknown_field": 42,
            "string_field": "test",
        }

        formatter = SummaryFormatter()
        result = pprint_json.humanize_data(data, formatter)

        assert result["average_pcpu"] == "85.57%"
        assert result["average_rss"] == "1.0 MB"
        assert result["wall_clock_time"] == "2m 30.8s"
        assert result["unknown_field"] == 42  # unchanged
        assert result["string_field"] == "test"  # unchanged

    def test_humanize_data_nested_structures(self) -> None:
        """Test humanize_data with nested dictionaries and lists"""

        data = {
            "process": {"peak_pcpu": 75.0, "average_vsz": 512000},
            "samples": [
                {"average_pcpu": 80.5, "peak_rss": 2048000},
                {"average_pcpu": 90.0, "peak_rss": 3072000},
            ],
        }

        formatter = SummaryFormatter()
        result = pprint_json.humanize_data(data, formatter)

        # Check nested dict
        assert result["process"]["peak_pcpu"] == "75.00%"
        assert result["process"]["average_vsz"] == "512.0 kB"

        # Check list of dicts
        assert result["samples"][0]["average_pcpu"] == "80.50%"
        assert result["samples"][0]["peak_rss"] == "2.0 MB"
        assert result["samples"][1]["average_pcpu"] == "90.00%"
        assert result["samples"][1]["peak_rss"] == "3.1 MB"

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"average_pcpu": 85.567, "average_rss": 1024000, "wall_clock_time": 150.75}',
    )
    @patch("con_duct.suite.pprint_json.pprint")
    def test_pprint_json_with_humanize(
        self, mock_pprint: MagicMock, mock_open: MagicMock
    ) -> None:
        """Test pprint_json with humanize=True"""
        args = argparse.Namespace(
            command="pp",
            file_path="dummy.json",
            func=pprint_json.pprint_json,
            log_level="NONE",
            humanize=True,
        )

        assert main.execute(args) == 0

        mock_open.assert_called_with("dummy.json", "r")

        # Verify that pprint was called with humanized data
        call_args = mock_pprint.call_args[0][0]
        assert call_args["average_pcpu"] == "85.57%"
        assert call_args["average_rss"] == "1.0 MB"
        assert call_args["wall_clock_time"] == "2m 30.8s"


class TestPlotMatplotlib(unittest.TestCase):

    @patch("matplotlib.pyplot.savefig")
    def test_matplotlib_plot_sanity(self, mock_plot_save: MagicMock) -> None:
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output="outfile.png",
            func=plot.matplotlib_plot,
            log_level="NONE",
        )
        assert main.execute(args) == 0
        mock_plot_save.assert_called_once_with("outfile.png")

    @patch("matplotlib.pyplot.savefig")
    def test_matplotlib_plot_file_not_found(self, mock_plot_save: MagicMock) -> None:
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage_not_to_be_found.json",
            output="outfile.png",
            func=plot.matplotlib_plot,
            log_level="NONE",
        )
        assert main.execute(args) == 1
        mock_plot_save.assert_not_called()

    @patch("matplotlib.pyplot.savefig")
    @patch("builtins.open", new_callable=mock_open, read_data='{"invalid": "json"')
    def test_matplotlib_plot_invalid_json(
        self, _mock_open: MagicMock, mock_plot_save: MagicMock
    ) -> None:
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output="outfile.png",
            func=plot.matplotlib_plot,
            log_level="NONE",
        )
        assert main.execute(args) == 1
        mock_plot_save.assert_not_called()

    @patch("matplotlib.pyplot.savefig")
    def test_matplotlib_plot_info_json(self, mock_plot_save: MagicMock) -> None:
        """When user passes info.json, usage.json is retrieved and used"""
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/info.json",
            output="outfile.png",
            func=plot.matplotlib_plot,
            log_level="NONE",
        )
        assert main.execute(args) == 0
        mock_plot_save.assert_called_once_with("outfile.png")

    @patch("matplotlib.pyplot.savefig")
    @patch(
        "builtins.open", new_callable=mock_open, read_data='{"missing": "timestamp"}'
    )
    def test_matplotlib_plot_malformed_usage_file(
        self, _mock_open: MagicMock, mock_plot_save: MagicMock
    ) -> None:
        """Test that malformed usage.json files are handled gracefully"""
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/malformed_usage.json",
            output="outfile.png",
            func=plot.matplotlib_plot,
            log_level="NONE",
        )
        assert main.execute(args) == 1
        mock_plot_save.assert_not_called()

    @patch(
        "matplotlib.get_backend",
        side_effect=AttributeError("get_backend not available"),
    )
    @patch.dict("matplotlib.rcParams", {"backend": "Agg"})
    def test_matplotlib_plot_non_interactive_backend(
        self,
        _mock_get_backend: MagicMock,
    ) -> None:
        """Test that plotting without output in non-interactive backend returns error."""

        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output=None,  # No output file specified
            func=plot.matplotlib_plot,
            log_level="NONE",
        )
        result = main.execute(args)
        assert result == 1

    @patch("matplotlib.get_backend", return_value="Agg")
    def test_matplotlib_plot_non_interactive_backend_with_get_backend(
        self,
        _mock_get_backend: MagicMock,
    ) -> None:
        """Test that plotting without output in non-interactive backend returns error using get_backend."""

        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output=None,  # No output file specified
            func=plot.matplotlib_plot,
            log_level="NONE",
        )
        result = main.execute(args)
        assert result == 1

    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.get_backend", return_value="tkagg")
    def test_matplotlib_plot_interactive_backend_with_get_backend(
        self,
        _mock_get_backend: MagicMock,
        mock_show: MagicMock,
    ) -> None:
        """Test that plotting without output in interactive backend calls plt.show() successfully."""

        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output=None,  # No output file specified
            func=plot.matplotlib_plot,
            log_level="NONE",
        )
        result = main.execute(args)
        assert result == 0
        mock_show.assert_called_once()

    @patch(
        "builtins.__import__", side_effect=ImportError("No module named 'matplotlib'")
    )
    def test_matplotlib_plot_missing_dependency(self, _mock_import: MagicMock) -> None:
        """Test that plotting with missing matplotlib shows helpful error."""
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output=None,
            func=plot.matplotlib_plot,
            log_level="NONE",
        )

        result = main.execute(args)
        assert result == 1


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
                reverse=False,
                func=ls,
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
            reverse=False,
            func=ls,
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
        result = self._run_ls(["file1_info.json"], "yaml")
        parsed = yaml.safe_load(result)
        assert len(parsed) == 1
        assert "prefix" in parsed[0]

    def test_ls_pyout_output(self) -> None:
        """Test YAML output format."""
        result = self._run_ls(["file1_info.json"], "pyout")
        # pyout header
        assert "PREFIX" in result
        assert os.path.join(self.temp_dir.name, "file1_") in result

    def test_ls_reverse_order(self) -> None:
        """Test that --reverse flag reverses the order of results."""
        paths = ["file1_info.json", "file2_info.json"]

        # Get normal order
        args_normal = argparse.Namespace(
            paths=[os.path.join(self.temp_dir.name, path) for path in paths],
            colors=False,
            fields=["prefix", "schema_version"],
            eval_filter=None,
            format="json",
            reverse=False,
            func=ls,
        )
        result_normal = self._run_ls(paths, "json", args_normal)
        parsed_normal = json.loads(result_normal)

        # Get reversed order
        args_reverse = argparse.Namespace(
            paths=[os.path.join(self.temp_dir.name, path) for path in paths],
            colors=False,
            fields=["prefix", "schema_version"],
            eval_filter=None,
            format="json",
            reverse=True,
            func=ls,
        )
        result_reverse = self._run_ls(paths, "json", args_reverse)
        parsed_reverse = json.loads(result_reverse)

        # Check that the order is actually reversed
        assert len(parsed_normal) == 2
        assert len(parsed_reverse) == 2
        assert parsed_normal[0]["prefix"] == parsed_reverse[1]["prefix"]
        assert parsed_normal[1]["prefix"] == parsed_reverse[0]["prefix"]

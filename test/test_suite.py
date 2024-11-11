import argparse
import contextlib
from io import StringIO
import json
import os
import tempfile
from typing import Any
import unittest
from unittest.mock import MagicMock, mock_open, patch
import pytest
import yaml
from con_duct.suite import main, plot, pprint_json
from con_duct.suite.ls import MINIMUM_SCHEMA_VERSION, ls


class TestSuiteHelpers(unittest.TestCase):

    def test_execute_returns_int(self) -> None:
        def return_non_int(*_args: Any) -> str:
            return "NOPE"

        args = argparse.Namespace(
            command="invalid", file_path="dummy.json", func=return_non_int
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
            command="pp", file_path="dummy.json", func=pprint_json.pprint_json
        )
        assert main.execute(args) == 0

        mock_open.assert_called_with("dummy.json", "r")
        mock_pprint.assert_called_once_with({"mock_key": "mock_value"})

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_file_not_found(self, _mock_open: MagicMock) -> None:
        args = argparse.Namespace(
            command="pp", file_path="dummy.json", func=pprint_json.pprint_json
        )
        assert main.execute(args) == 1

    @patch("builtins.open", new_callable=mock_open, read_data='{"invalid": "json"')
    @patch("con_duct.suite.pprint_json.pprint")
    def test_pprint_invalid_json(
        self, mock_pprint: MagicMock, mock_open: MagicMock
    ) -> None:
        args = argparse.Namespace(
            command="pp", file_path="dummy.json", func=pprint_json.pprint_json
        )
        assert main.execute(args) == 1

        mock_open.assert_called_with("dummy.json", "r")
        mock_pprint.assert_not_called()


class TestPlotMatplotlib(unittest.TestCase):

    @patch("matplotlib.pyplot.savefig")
    def test_matplotlib_plot_sanity(self, mock_plot_save: MagicMock) -> None:
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output="outfile.png",
            func=plot.matplotlib_plot,
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
        )
        assert main.execute(args) == 1
        mock_plot_save.assert_not_called()


class TestLS(unittest.TestCase):
    def setUp(self) -> None:
        """Create a temporary directory and test files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.files = {
            "file1_info.json": {
                "schema_version": MINIMUM_SCHEMA_VERSION,
                "prefix": "test1",
            },
            "file2_info.json": {
                "schema_version": MINIMUM_SCHEMA_VERSION,
                "prefix": "test2",
            },
            "file3_info.json": {"schema_version": "0.1.0", "prefix": "old_version"},
            "not_matching.json": {
                "schema_version": MINIMUM_SCHEMA_VERSION,
                "prefix": "no_match",
            },
        }
        for filename, content in self.files.items():
            with open(os.path.join(self.temp_dir.name, filename), "w") as f:
                json.dump(content, f)

    def tearDown(self) -> None:
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def _run_ls(self, paths: list[str], fmt: str) -> str:
        """Helper function to run ls() and capture stdout."""
        args = argparse.Namespace(
            paths=[os.path.join(self.temp_dir.name, path) for path in paths],
            colors=False,
            fields=["prefix", "schema_version"],
            format=fmt,
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

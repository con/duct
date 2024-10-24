import argparse
from typing import Any
import unittest
from unittest.mock import MagicMock, mock_open, patch
import pytest
from con_duct.suite import main, plot, pprint_json


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

    @patch("con_duct.suite.plot.plt.savefig")
    def test_matplotlib_plot_sanity(self, mock_plot_save: MagicMock) -> None:
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output="outfile",
            func=plot.matplotlib_plot,
        )
        assert main.execute(args) == 0
        mock_plot_save.assert_called_once_with("outfile")

    @patch("con_duct.suite.plot.plt.savefig")
    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_matplotlib_plot_file_not_found(
        self, _mock_open: MagicMock, mock_plot_save: MagicMock
    ) -> None:
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output="outfile",
            func=plot.matplotlib_plot,
        )
        assert main.execute(args) == 1
        mock_plot_save.assert_not_called()

    @patch("con_duct.suite.plot.plt.savefig")
    @patch("builtins.open", new_callable=mock_open, read_data='{"invalid": "json"')
    def test_matplotlib_plot_invalid_json(
        self, _mock_open: MagicMock, mock_plot_save: MagicMock
    ) -> None:
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output="outfile",
            func=plot.matplotlib_plot,
        )
        assert main.execute(args) == 1
        mock_plot_save.assert_not_called()

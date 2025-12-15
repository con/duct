"""Tests for plot command."""

import argparse
import os
from typing import Any, List, Tuple
from unittest.mock import MagicMock, Mock, mock_open, patch
import pytest

pytest.importorskip("matplotlib")
from con_duct import cli, plot  # noqa: E402


@pytest.mark.parametrize(
    "min_ratio,span_seconds,expected_unit",
    [
        # min_ratio=-1: always use base unit
        (-1, 2, "s"),  # Small value
        (-1, 3700, "s"),  # More than 1 hour - still base unit
        (-1, 3 * 60 * 60 * 24, "s"),  # 3 days - still base unit
        # min_ratio=1.5: switch units more aggressively
        (1.5, 90, "min"),  # 1.5 minutes meets threshold
        (1.5, 90 * 60, "h"),  # 1.5 hours meets threshold
        (1.5, 36 * 60 * 60, "d"),  # 1.5 days meets threshold
        # min_ratio=3.0: standard threshold
        (3.0, 2, "s"),  # 2 seconds - stays in base unit
        (3.0, 3 * 60, "min"),  # 3 minutes - meets min_ratio for minutes
        (3.0, 3 * 60 * 60, "h"),  # 3 hours - meets min_ratio for hours
        (3.0, 3 * 60 * 60 * 24, "d"),  # 3 days - meets min_ratio for days
        # min_ratio=5.0: more conservative switching
        (5.0, 4 * 60, "s"),  # 4 minutes - doesn't meet threshold, stays seconds
        (5.0, 5 * 60, "min"),  # 5 minutes - meets threshold
        (5.0, 4 * 60 * 60, "min"),  # 4 hours - doesn't meet hour threshold
        (5.0, 5 * 60 * 60, "h"),  # 5 hours - meets hour threshold
    ],
)
def test_pick_unit_with_varying_ratios(
    min_ratio: float, span_seconds: float, expected_unit: str
) -> None:
    """Test pick_unit selects appropriate unit based on min_ratio."""
    formatter: Any = plot.HumanizedAxisFormatter(
        min_ratio=min_ratio, units=plot._TIME_UNITS
    )
    unit_name, _ = formatter.pick_unit(span_seconds)
    assert unit_name == expected_unit


@pytest.mark.parametrize(
    "units,axis_range,value,expected",
    [
        # Time formatting tests
        (plot._TIME_UNITS, (0, 30), 15, "15.0s"),
        (plot._TIME_UNITS, (0, 300), 2.3 * 60, "2.3min"),
        (plot._TIME_UNITS, (0, 11000), 7.8 * 60 * 60, "7.8h"),
        (plot._TIME_UNITS, (0, 260000), 3.2 * 60 * 60 * 24, "3.2d"),
        # Memory formatting tests
        (plot._MEMORY_UNITS, (0, 5 * 1024), 2.6 * 1024, "2.6KB"),
        (plot._MEMORY_UNITS, (0, 4 * 1024**2), 1.5 * (1024**2), "1.5MB"),
        (plot._MEMORY_UNITS, (0, 3 * 1024**3), 8.3 * 1024**3, "8.3GB"),
        (plot._MEMORY_UNITS, (0, 3 * 1024**4), 1.3 * 1024**4, "1.3TB"),
        (plot._MEMORY_UNITS, (0, 3.1 * 1024**5), 6.5 * 1024**5, "6.5PB"),
    ],
)
def test_formatter_output(
    units: List[Tuple[str, float]],
    axis_range: Tuple[float, float],
    value: float,
    expected: str,
) -> None:
    """Test HumanizedAxisFormatter formats values correctly for time and memory units."""
    formatter: Any = plot.HumanizedAxisFormatter(min_ratio=3.0, units=units)
    formatter.axis = Mock()
    formatter.axis.get_view_interval.return_value = axis_range
    result = formatter(value, 0)
    assert result == expected


class TestPlotMatplotlib:

    @patch("matplotlib.pyplot.savefig")
    def test_matplotlib_plot_sanity(self, mock_plot_save: MagicMock) -> None:
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output="outfile.png",
            func=plot.matplotlib_plot,
            log_level="INFO",
            min_ratio=3.0,
        )
        assert cli.execute(args) == 0
        mock_plot_save.assert_called_once_with("outfile.png")

    @patch("matplotlib.pyplot.savefig")
    @patch("matplotlib.use")
    def test_matplotlib_plot_uses_agg_backend_with_output(
        self, mock_use: MagicMock, mock_plot_save: MagicMock
    ) -> None:
        """Test that Agg backend is used when --output is specified."""
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output="outfile.png",
            func=plot.matplotlib_plot,
            log_level="INFO",
            min_ratio=3.0,
        )
        assert cli.execute(args) == 0
        mock_use.assert_called_once_with("Agg")
        mock_plot_save.assert_called_once_with("outfile.png")

    @patch("matplotlib.pyplot.savefig")
    def test_matplotlib_plot_file_not_found(self, mock_plot_save: MagicMock) -> None:
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage_not_to_be_found.json",
            output="outfile.png",
            func=plot.matplotlib_plot,
            log_level="INFO",
        )
        assert cli.execute(args) == 1
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
            log_level="INFO",
        )
        assert cli.execute(args) == 1
        mock_plot_save.assert_not_called()

    @patch("matplotlib.pyplot.savefig")
    def test_matplotlib_plot_info_json(self, mock_plot_save: MagicMock) -> None:
        """When user passes info.json, usage.json is retrieved and used"""
        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/info.json",
            output="outfile.png",
            func=plot.matplotlib_plot,
            log_level="INFO",
            min_ratio=3.0,
        )
        assert cli.execute(args) == 0
        mock_plot_save.assert_called_once_with("outfile.png")

    @patch("matplotlib.pyplot.savefig")
    def test_matplotlib_plot_info_json_absolute_path(
        self, mock_plot_save: MagicMock, monkeypatch: Any, tmp_path: Any
    ) -> None:
        """Test that absolute path to info.json correctly resolves usage.json path
        when cwd is not the original execution wd.
        """
        abs_info_path = os.path.abspath("test/data/mriqc-example/info.json")

        # change into a pytest-managed temporary directory
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(
            command="plot",
            file_path=abs_info_path,
            output="outfile.png",
            func=plot.matplotlib_plot,
            log_level="INFO",
            min_ratio=3.0,
        )
        assert cli.execute(args) == 0
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
            log_level="INFO",
        )
        assert cli.execute(args) == 1
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
        import matplotlib.backends

        if not hasattr(matplotlib.backends, "backend_registry"):
            pytest.skip("requires backend_registry (matplotlib >= 3.9)")

        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output=None,  # No output file specified
            func=plot.matplotlib_plot,
            log_level="INFO",
            min_ratio=3.0,
        )
        result = cli.execute(args)
        assert result == 1

    @patch("matplotlib.get_backend", return_value="Agg")
    def test_matplotlib_plot_non_interactive_backend_with_get_backend(
        self,
        _mock_get_backend: MagicMock,
    ) -> None:
        """Test that plotting without output in non-interactive backend returns error using get_backend."""
        import matplotlib.backends

        if not hasattr(matplotlib.backends, "backend_registry"):
            pytest.skip("requires backend_registry (matplotlib >= 3.9)")

        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output=None,  # No output file specified
            func=plot.matplotlib_plot,
            log_level="INFO",
            min_ratio=3.0,
        )
        result = cli.execute(args)
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
            log_level="INFO",
            min_ratio=3.0,
        )
        result = cli.execute(args)
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
            log_level="INFO",
        )

        result = cli.execute(args)
        assert result == 1

    @patch("matplotlib.pyplot.show")
    def test_matplotlib_plot_no_backend_registry(
        self,
        mock_show: MagicMock,
        monkeypatch: Any,
        caplog: Any,
    ) -> None:
        """Test fallback when backend_registry unavailable (matplotlib < 3.9)."""
        import matplotlib.backends

        # Only delete if present (already absent on matplotlib < 3.9)
        if hasattr(matplotlib.backends, "backend_registry"):
            monkeypatch.delattr(matplotlib.backends, "backend_registry")

        args = argparse.Namespace(
            command="plot",
            file_path="test/data/mriqc-example/usage.json",
            output=None,
            func=plot.matplotlib_plot,
            log_level="INFO",
            min_ratio=3.0,
        )
        result = cli.execute(args)
        assert result == 0
        mock_show.assert_called_once()
        assert "matplotlib < 3.9" in caplog.text

import argparse
from typing import Any
import unittest
from unittest.mock import MagicMock, mock_open, patch
from con_duct import cli, pprint_json
from con_duct.duct_main import SummaryFormatter


class TestPPrint:

    @patch("con_duct.pprint_json.pprint")
    def test_pprint_json(self, mock_pprint: MagicMock, tmp_path: Any) -> None:
        json_file = tmp_path / "test.json"
        json_file.write_text('{"mock_key": "mock_value"}')

        args = argparse.Namespace(
            command="pp",
            file_path=str(json_file),
            func=pprint_json.pprint_json,
            log_level="INFO",
            humanize=False,
        )
        assert cli.execute(args) == 0
        mock_pprint.assert_called_once_with({"mock_key": "mock_value"})

    @patch("con_duct.pprint_json.pprint")
    def test_pprint_jsonl(self, mock_pprint: MagicMock, tmp_path: Any) -> None:
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text('{"line": 1}\n{"line": 2}\n')

        args = argparse.Namespace(
            command="pp",
            file_path=str(jsonl_file),
            func=pprint_json.pprint_json,
            log_level="INFO",
            humanize=False,
        )
        assert cli.execute(args) == 0
        mock_pprint.assert_called_once_with([{"line": 1}, {"line": 2}])

    def test_file_not_found(self) -> None:
        args = argparse.Namespace(
            command="pp",
            file_path="/nonexistent/path.json",
            func=pprint_json.pprint_json,
            log_level="INFO",
            humanize=False,
        )
        assert cli.execute(args) == 1

    @patch("con_duct.pprint_json.pprint")
    def test_pprint_invalid_json(self, mock_pprint: MagicMock, tmp_path: Any) -> None:
        json_file = tmp_path / "invalid.json"
        json_file.write_text('{"invalid": "json"')

        args = argparse.Namespace(
            command="pp",
            file_path=str(json_file),
            func=pprint_json.pprint_json,
            log_level="INFO",
            humanize=False,
        )
        assert cli.execute(args) == 1
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
    @patch("con_duct.pprint_json.pprint")
    def test_pprint_json_with_humanize(
        self, mock_pprint: MagicMock, mock_open: MagicMock
    ) -> None:
        """Test pprint_json with humanize=True"""
        args = argparse.Namespace(
            command="pp",
            file_path="dummy.json",
            func=pprint_json.pprint_json,
            log_level="INFO",
            humanize=True,
        )

        assert cli.execute(args) == 0

        mock_open.assert_called_with("dummy.json", "r")

        # Verify that pprint was called with humanized data
        call_args = mock_pprint.call_args[0][0]
        assert call_args["average_pcpu"] == "85.57%"
        assert call_args["average_rss"] == "1.0 MB"
        assert call_args["wall_clock_time"] == "2m 30.8s"

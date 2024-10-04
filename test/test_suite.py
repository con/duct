import argparse
import unittest
from unittest.mock import mock_open, patch
from con_duct import suite


class TestPPrint(unittest.TestCase):

    @patch(
        "builtins.open", new_callable=mock_open, read_data='{"mock_key": "mock_value"}'
    )
    @patch("con_duct.suite.pprint")
    def test_pprint_json(self, mock_pprint, mock_open):
        args = argparse.Namespace(
            command="pp", file_path="dummy.json", func=suite.pprint_json
        )
        assert suite.execute(args) == 0

        mock_open.assert_called_with("dummy.json", "r")
        mock_pprint.assert_called_once_with({"mock_key": "mock_value"})

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_file_not_found(self, _mock_open):
        # Simulate argparse returning the necessary arguments for the 'pp' subcommand
        args = argparse.Namespace(
            command="pp", file_path="dummy.json", func=suite.pprint_json
        )
        assert suite.execute(args) == 1

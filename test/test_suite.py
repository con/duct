import argparse
import unittest
from unittest.mock import mock_open, patch
from con_duct import suite


class TestSuiteCommands(unittest.TestCase):

    @patch("con_duct.suite.argparse.ArgumentParser.parse_args")
    @patch(
        "builtins.open", new_callable=mock_open, read_data='{"mock_key": "mock_value"}'
    )
    @patch("con_duct.suite.pprint")
    def test_pprint_json(self, mock_pprint, mock_open, mock_args):
        mock_args.return_value = argparse.Namespace(
            command="pp", file_path="dummy.json", func=suite.pprint_json
        )
        suite.main()

        mock_open.assert_called_with("dummy.json", "r")
        mock_pprint.assert_called_once_with({"mock_key": "mock_value"})

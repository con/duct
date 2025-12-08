import json
import os
from pathlib import Path
from utils import run_duct_command
from con_duct.duct_main import SUFFIXES
from con_duct.ls import LS_FIELD_CHOICES, _flatten_dict


def test_info_fields(temp_output_dir: str) -> None:
    """
    Generate the list of fields users can request when viewing info files.

    Fails when schema changes-- commit the new version and bump schema version
    """
    assert (
        run_duct_command(
            ["echo", "hello", "world"],
            sample_interval=4.0,
            report_interval=60.0,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    os.remove(Path(temp_output_dir, SUFFIXES["stdout"]))
    os.remove(Path(temp_output_dir, SUFFIXES["stderr"]))
    os.remove(Path(temp_output_dir, SUFFIXES["usage"]))

    info_file = Path(temp_output_dir, SUFFIXES["info"])
    actual_info_schema = _flatten_dict(json.loads(info_file.read_text())).keys()
    os.remove(info_file)

    assert set(actual_info_schema) == set(LS_FIELD_CHOICES)

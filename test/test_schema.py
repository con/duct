import json
import os
from pathlib import Path
from con_duct.__main__ import Arguments, execute
from con_duct.suite.ls import LS_FIELD_CHOICES, _flatten_dict


def test_info_fields(temp_output_dir: str) -> None:
    """
    Generate the list of fields users can request when viewing info files.

    Fails when schema changes-- commit the new version and bump schema version
    """
    args = Arguments.from_argv(
        ["echo", "hello", "world"],
        sample_interval=4.0,
        report_interval=60.0,
        output_prefix=temp_output_dir,
        clobber=True,
    )
    # Execute duct
    assert execute(args) == 0  # exit_code
    os.remove(Path(temp_output_dir, "stdout"))
    os.remove(Path(temp_output_dir, "stderr"))
    os.remove(Path(temp_output_dir, "usage.json"))

    info_file = Path(temp_output_dir, "info.json")
    actual_info_schema = _flatten_dict(json.loads(info_file.read_text())).keys()
    os.remove(info_file)

    assert set(actual_info_schema) == set(LS_FIELD_CHOICES)

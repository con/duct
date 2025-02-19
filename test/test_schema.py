import json
import os
from pathlib import Path
from con_duct.__main__ import Arguments, execute
from con_duct.suite.ls import LS_FIELD_CHOICES, _flatten_dict
from con_duct.utils import SCHEMA_DIR, read_list_from_file, write_list_to_file


def test_info_fields() -> None:
    """
    Generate the list of fields users can request when viewing info files.

    Fails when schema changes-- commit the new version and bump schema version
    """
    args = Arguments.from_argv(
        ["echo", "hello", "world"],
        sample_interval=4.0,
        report_interval=60.0,
        output_prefix=SCHEMA_DIR,
        clobber=True,
    )
    # Execute duct
    assert execute(args) == 0  # exit_code
    os.remove(Path(SCHEMA_DIR, "stdout"))
    os.remove(Path(SCHEMA_DIR, "stderr"))
    os.remove(Path(SCHEMA_DIR, "usage.json"))
    info_file = Path(SCHEMA_DIR, "info.json")

    info_fields_schema_file = Path(SCHEMA_DIR, "info_schema.txt")

    expected_info_fields_schema = read_list_from_file(info_fields_schema_file)

    actual_info_schema = _flatten_dict(json.loads(info_file.read_text())).keys()
    os.remove(info_file)

    write_list_to_file(actual_info_schema, info_fields_schema_file)
    assert set(expected_info_fields_schema) == set(actual_info_schema)
    assert set(expected_info_fields_schema) == set(LS_FIELD_CHOICES)

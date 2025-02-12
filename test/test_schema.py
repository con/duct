import json
import os
from pathlib import Path
from con_duct.__main__ import Arguments, execute
from con_duct.suite.ls import _flatten_dict


#
# TEST_SCRIPT = str(Path(__file__).with_name("data") / "test_script.py")
#
# expected_files = [
#     SUFFIXES["stdout"],
#     SUFFIXES["stderr"],
#     SUFFIXES["info"],
#     SUFFIXES["usage"],
# ]
#
#
# def assert_expected_files(temp_output_dir: str, exists: bool = True) -> None:
#     assert_files(temp_output_dir, expected_files, exists=exists)
def write_list_to_file(items, path: Path):
    with path.open("w") as f:
        for item in items:
            f.write(f"{item}\n")


def read_list_from_file(path: Path):
    with path.open("r") as f:
        return [line.strip() for line in f]


def test_info_fields() -> None:
    """
    Generate the list of fields users can request when viewing info files.

    Fails when schema changes-- commit the new version and bump schema version
    """
    SCHEMA_TEST = "test/data/schema_test/"
    args = Arguments.from_argv(
        ["echo", "hello", "world"],
        sample_interval=4.0,
        report_interval=60.0,
        output_prefix=SCHEMA_TEST,
        clobber=True,
    )
    # Execute duct
    assert execute(args) == 0  # exit_code
    os.remove(Path(SCHEMA_TEST, "stdout"))
    os.remove(Path(SCHEMA_TEST, "stderr"))
    os.remove(Path(SCHEMA_TEST, "usage.json"))
    info_file = Path(SCHEMA_TEST, "info.json")

    info_fields_schema_file = Path(SCHEMA_TEST, "info_schema.txt")

    expected_info_fields_schema = read_list_from_file(info_fields_schema_file)

    actual_info_schema = _flatten_dict(json.loads(info_file.read_text())).keys()
    os.remove(info_file)

    write_list_to_file(actual_info_schema, info_fields_schema_file)
    assert set(expected_info_fields_schema) == set(actual_info_schema)

import json
import os
from pathlib import Path
from utils import run_duct_command
from con_duct.duct_main import SUFFIXES
from con_duct.ls import LS_FIELD_CHOICES, OPTIONAL_GPU_FIELDS, _flatten_dict


def test_info_fields(temp_output_dir: str) -> None:
    """
    Generate the list of fields users can request when viewing info files.

    Fails when schema changes-- commit the new version and bump schema version.
    GPU fields are optional and only present when GPU monitoring is enabled.
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
    actual_info_schema = set(_flatten_dict(json.loads(info_file.read_text())).keys())
    os.remove(info_file)

    # GPU fields are optional - they only appear when GPU monitoring is enabled
    expected_required_fields = set(LS_FIELD_CHOICES) - set(OPTIONAL_GPU_FIELDS)
    expected_optional_fields = set(OPTIONAL_GPU_FIELDS)

    # All required fields must be present
    assert (
        expected_required_fields <= actual_info_schema
    ), f"Missing required fields: {expected_required_fields - actual_info_schema}"
    # Any extra fields must be from the optional set
    extra_fields = actual_info_schema - expected_required_fields
    assert (
        extra_fields <= expected_optional_fields
    ), f"Unexpected fields: {extra_fields - expected_optional_fields}"

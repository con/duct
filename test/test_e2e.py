from __future__ import annotations
from itertools import chain
import json
from pathlib import Path
import subprocess
import pytest

ABANDONING_PARENT = str(Path(__file__).with_name("data") / "abandoning_parent.sh")


def test_sanity(temp_output_dir: str) -> None:
    command = f"duct -p {temp_output_dir}log_ sleep 0.1"
    subprocess.check_output(command, shell=True)


@pytest.mark.parametrize("num_children", [1, 2, 10])
def test_abandoning_parent(temp_output_dir: str, num_children: int) -> None:
    duct_prefix = f"{temp_output_dir}log_"
    command = f"duct --s-i 0.001 --r-i 0.01 -p {duct_prefix} {ABANDONING_PARENT} {num_children} sleep 0.2"
    subprocess.check_output(command, shell=True)

    with open(f"{duct_prefix}usage.json") as usage_file:
        all_samples = [json.loads(line) for line in usage_file]

    all_pids = set(chain.from_iterable(sample["processes"] for sample in all_samples))

    # 1 for each child, 1 for pstree, 1 for parent
    assert len(all_pids) == num_children + 2

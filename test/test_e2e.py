from __future__ import annotations
import json
from pathlib import Path
import subprocess

ABANDONING_PARENT = str(Path(__file__).with_name("data") / "abandoning_parent.sh")


def test_sanity(temp_output_dir: str) -> None:
    command = f"duct -p {temp_output_dir}log_ sleep 0.1"
    subprocess.check_output(command, shell=True)


def test_abandoning_parent(temp_output_dir: str) -> None:
    duct_prefix = f"{temp_output_dir}log_"
    num_children = 3
    command = f"duct -p {duct_prefix} {ABANDONING_PARENT} {num_children} sleep 0.1"
    subprocess.check_output(command, shell=True)

    with open(f"{duct_prefix}usage.json") as usage_file:
        all_samples = [json.loads(line) for line in usage_file]

    max_processes_sample = {"processes": {}}
    for sample in all_samples:
        if len(max_processes_sample) < len(sample.get("processes")):
            max_processes_sample = sample

    # 1 for each child, 1 for pstree, 1 for parent
    assert len(max_processes_sample) == num_children + 2

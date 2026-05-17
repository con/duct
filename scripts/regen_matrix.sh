#!/usr/bin/env bash
# Regenerate sampler matrix CSVs from a fresh test run.
#
# Canonical invocation (records command + inputs/outputs as provenance):
#
#     datalad run scripts/regen_matrix.sh
#
# Plain invocation also works; you lose the datalad-run metadata but
# the CSVs are identical.
#
# Requirements on the host:
#   - .tox/py312 present (run `tox -e py312` once if absent)
#   - systemd-run --user --scope working, for the opt-in cgroup_matrix
#     tests (hosts without user systemd skip those tests, and the
#     cgroup column stays at its prior values / (not yet tested))
#
# The script runs the matrix tests with --cgroup-matrix and invokes the
# CSV generator. Both are fast (<20 s combined) against an already-
# populated .tox/py312 env.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

.tox/py312/bin/python -m pytest \
    -o addopts= \
    --cgroup-matrix \
    test/duct_main/test_sampler_matrix.py

python3 scripts/gen_sampler_matrix.py

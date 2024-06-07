from collections import defaultdict
from duct import Report

ex0 = {"pid1": {"pcpu": 0.0}}
ex1 = {"pid1": {"pcpu": 1.0}}
ex2 = {"pid2": {"pcpu": 1.0}}
ex2pids = {"pid1": {"pcpu": 0.0}, "pid2": {"pcpu": 0.0}}


def test_update_max_resources_initial_values_one_pid():
    maxes = defaultdict(dict)
    Report.update_max_resources(maxes, ex0)
    assert maxes == ex0


def test_update_max_resources_max_values_one_pid():
    maxes = defaultdict(dict)
    Report.update_max_resources(maxes, ex0)
    Report.update_max_resources(maxes, ex1)
    assert maxes == ex1


def test_update_max_resources_initial_values_two_pids():
    maxes = defaultdict(dict)
    Report.update_max_resources(maxes, ex2pids)
    assert maxes == ex2pids


def test_update_max_resources_max_update_values_two_pids():
    maxes = defaultdict(dict)
    Report.update_max_resources(maxes, ex2pids)
    Report.update_max_resources(maxes, ex1)
    Report.update_max_resources(maxes, ex2)
    assert maxes.keys() == ex2pids.keys()
    assert maxes != ex2pids
    assert maxes["pid1"] == ex1["pid1"]
    assert maxes["pid2"] == ex2["pid2"]

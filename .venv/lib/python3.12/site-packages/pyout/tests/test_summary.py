from pyout.summary import Summary


def eq(result, expect):
    """Unwrap summarize `result` and assert that it is equal to `expect`.
    """
    assert [r[0] for r in result] == expect


def test_summary_summarize_no_agg_columns():
    sm = Summary({"col1": {}})
    eq(sm.summarize(["col1"],
                    [{"col1": "a"},
                     {"col1": "b"}]),
       [])


def test_summary_summarize_atom_return():
    sm = Summary({"col1": {"aggregate": len}})
    eq(sm.summarize(["col1"],
                    [{"col1": "a"},
                     {"col1": "b"}]),
       [{"col1": 2}])


def test_summary_summarize_list_return():
    def unique_lens(xs):
        return list(sorted(set(map(len, xs))))

    sm = Summary({"col1": {"aggregate": unique_lens}})
    eq(sm.summarize(["col1"],
                    [{"col1": "a"},
                     {"col1": "bcd"},
                     {"col1": "ef"},
                     {"col1": "g"}]),
       [{"col1": 1},
        {"col1": 2},
        {"col1": 3}])


def test_summary_summarize_multicolumn_return():
    def unique_values(xs):
        return list(sorted(set(xs)))

    sm = Summary({"col1": {"aggregate": unique_values},
                  "col2": {"aggregate": len},
                  "col3": {"aggregate": unique_values}})
    eq(sm.summarize(["col1", "col2", "col3"],
                    [{"col1": "a", "col2": "x", "col3": "c"},
                     {"col1": "b", "col2": "y", "col3": "c"},
                     {"col1": "a", "col2": "z", "col3": "c"}]),
       [{"col1": "a", "col2": 3, "col3": "c"},
        {"col1": "b", "col2": "", "col3": ""}])

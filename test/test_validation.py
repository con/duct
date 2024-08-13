import argparse
import pytest
from con_duct.__main__ import Arguments, Outputs, RecordTypes, assert_num


def test_sample_less_than_report_interval() -> None:
    args = Arguments(
        command="fake",
        command_args=[],
        output_prefix="fake",
        sample_interval=0.01,
        report_interval=0.1,
        capture_outputs=Outputs.NONE,
        outputs=Outputs.ALL,
        record_types=RecordTypes.SYSTEM_SUMMARY,
        summary_format="",
        quiet=False,
        clobber=False,
    )
    assert args.sample_interval <= args.report_interval


def test_sample_equal_to_report_interval() -> None:
    args = Arguments(
        command="fake",
        command_args=[],
        output_prefix="fake",
        sample_interval=0.1,
        report_interval=0.1,
        capture_outputs=Outputs.NONE,
        outputs=Outputs.ALL,
        record_types=RecordTypes.SYSTEM_SUMMARY,
        clobber=False,
        summary_format="",
        quiet=False,
    )
    assert args.sample_interval == args.report_interval


def test_sample_equal_greater_than_report_interval() -> None:
    with pytest.raises(argparse.ArgumentError):
        Arguments(
            command="fake",
            command_args=[],
            output_prefix="fake",
            sample_interval=1.0,
            report_interval=0.1,
            capture_outputs=Outputs.NONE,
            outputs=Outputs.ALL,
            record_types=RecordTypes.SYSTEM_SUMMARY,
            clobber=False,
            summary_format="",
            quiet=False,
        )


@pytest.mark.parametrize("input_value", [0, 1, 2, -1, 100, 0.001, -1.68])
def test_assert_num_green(input_value: int) -> None:
    assert_num(input_value)


@pytest.mark.parametrize("input_value", ["hi", "0", "one"])
def test_assert_num_red(input_value: int) -> None:
    with pytest.raises(AssertionError):
        assert_num(input_value)

import pytest
from utils import run_duct_command
from con_duct.duct_main import assert_num


def test_sample_less_than_report_interval(temp_output_dir: str) -> None:
    run_duct_command(
        ["echo", "test"],
        sample_interval=0.01,
        report_interval=0.1,
        output_prefix=temp_output_dir,
    )


def test_sample_equal_to_report_interval(temp_output_dir: str) -> None:
    run_duct_command(
        ["echo", "test"],
        sample_interval=0.1,
        report_interval=0.1,
        output_prefix=temp_output_dir,
    )


def test_sample_equal_greater_than_report_interval() -> None:
    with pytest.raises(
        ValueError,
        match="--report-interval must be greater than or equal to --sample-interval",
    ):
        run_duct_command(
            ["echo", "test"],
            sample_interval=1.0,
            report_interval=0.1,
        )


@pytest.mark.parametrize("input_value", [0, 1, 2, -1, 100, 0.001, -1.68])
def test_assert_num_green(input_value: int) -> None:
    assert_num(input_value)


@pytest.mark.parametrize("input_value", ["hi", "0", "one"])
def test_assert_num_red(input_value: int) -> None:
    with pytest.raises(AssertionError):
        assert_num(input_value)

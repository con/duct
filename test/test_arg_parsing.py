import subprocess
import pytest


def test_duct_help() -> None:
    out = subprocess.check_output(["duct", "--help", "ps"])
    assert "usage: duct [-h]" in str(out)


def test_cmd_help() -> None:
    out = subprocess.check_output(["duct", "ps", "--help"])
    assert "ps [options]" in str(out)
    assert "usage: duct [-h]" not in str(out)


@pytest.mark.parametrize(
    "args",
    [
        ["duct", "--unknown", "ps"],
        ["duct", "--unknown", "ps", "--shouldhavenoeffect"],
    ],
)
def test_duct_unrecognized_arg(args: list) -> None:
    try:
        subprocess.check_output(args, stderr=subprocess.STDOUT)
        pytest.fail("Command should have failed with a non-zero exit code")
    except subprocess.CalledProcessError as e:
        assert e.returncode == 2
        assert "duct: error: unrecognized arguments: --unknown" in str(e.stdout)


def test_duct_missing_cmd() -> None:
    try:
        subprocess.check_output(
            ["duct", "--sample-interval", "1"], stderr=subprocess.STDOUT
        )
        pytest.fail("Command should have failed with a non-zero exit code")
    except subprocess.CalledProcessError as e:
        assert e.returncode == 2
        assert "duct: error: the following arguments are required: command" in str(
            e.stdout
        )


def test_abreviation_disabled() -> None:
    """
    If abbreviation is enabled, options passed to command (not duct) are still
    filtered through the argparse and causes problems.
    """
    try:
        subprocess.check_output(["duct", "ps", "--output"], stderr=subprocess.STDOUT)
        raise AssertionError("Invocation of 'ps' should have failed")
    except subprocess.CalledProcessError as e:
        assert e.returncode == 1
        assert "duct: error: ambiguous option: --output could match" not in str(
            e.stdout
        )
        assert "ps [options]" in str(e.stdout)

import pytest
from con_duct.utils import parse_version


@pytest.mark.parametrize(
    ("lesser", "greater"),
    [
        ("0.0.0", "1.0.0"),  # sanity
        ("0.2.0", "0.12.0"),  # each should value should be treated as an int
        ("0.99.99", "1.0.0"),  # X matters more than Y or Z
        ("0.0.99", "0.1.0"),  # Y matters more than Z
        ("3.2.1", "3.2.01"),  # Leading zeros are ok
    ],
)
def test_parse_version_green(lesser: str, greater: str) -> None:
    assert parse_version(greater) >= parse_version(lesser)


@pytest.mark.parametrize(
    ("invalid"),
    [
        "1",
        "1.1.1.1",  # Four shalt thou not count
        "1.1",  #  neither count thou two, excepting that thou then proceed to three
        "5.4.3.2.1",  # Five is right out
    ],
)
def test_parse_version_invalid_length(invalid: str) -> None:
    with pytest.raises(ValueError, match="Invalid version format"):
        parse_version(invalid)


@pytest.mark.parametrize(
    ("invalid"),
    [
        "a.b.c",
        "1.2.3a1",
    ],
)
def test_parse_version_invalid_type(invalid: str) -> None:
    with pytest.raises(ValueError, match="invalid literal for int"):
        parse_version(invalid)

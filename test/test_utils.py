import pytest
from pathlib import Path
from con_duct.utils import parse_version, is_jsonl_file, load_json_or_jsonl
import tempfile
import json


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


class TestIsJsonlFile:
    """Test the is_jsonl_file utility function"""
    
    @pytest.mark.parametrize(
        "file_path,expected",
        [
            ("usage.jsonl", True),
            ("test_usage.jsonl", True),
            ("path/to/usage.jsonl", True),
            ("usage.json", True),  # Legacy support for usage.json
            ("test_usage.json", True),  # Legacy support for *_usage.json
            ("path/to/test_usage.json", True),
            ("info.json", False),
            ("data.json", False),
            ("file.txt", False),
            ("usage.txt", False),
        ],
    )
    def test_is_jsonl_file(self, file_path: str, expected: bool) -> None:
        assert is_jsonl_file(file_path) == expected
    
    def test_is_jsonl_file_with_path_object(self) -> None:
        assert is_jsonl_file(Path("usage.jsonl")) is True
        assert is_jsonl_file(Path("info.json")) is False


class TestLoadJsonOrJsonl:
    """Test the load_json_or_jsonl utility function"""
    
    def test_load_regular_json(self) -> None:
        """Test loading a regular JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"key": "value", "number": 42}, f)
            temp_path = f.name
        
        try:
            data = load_json_or_jsonl(temp_path)
            assert data == {"key": "value", "number": 42}
        finally:
            Path(temp_path).unlink()
    
    def test_load_jsonl_file(self) -> None:
        """Test loading a JSON Lines file (.jsonl extension)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"line": 1}\n')
            f.write('{"line": 2}\n')
            f.write('{"line": 3}\n')
            temp_path = f.name
        
        try:
            data = load_json_or_jsonl(temp_path)
            assert data == [{"line": 1}, {"line": 2}, {"line": 3}]
        finally:
            Path(temp_path).unlink()
    
    def test_load_usage_json_as_jsonl(self) -> None:
        """Test loading usage.json as JSON Lines (legacy support)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='_usage.json', delete=False) as f:
            f.write('{"timestamp": "2024-01-01"}\n')
            f.write('{"timestamp": "2024-01-02"}\n')
            temp_path = f.name
        
        try:
            data = load_json_or_jsonl(temp_path)
            assert data == [{"timestamp": "2024-01-01"}, {"timestamp": "2024-01-02"}]
        finally:
            Path(temp_path).unlink()
    
    def test_load_jsonl_with_empty_lines(self) -> None:
        """Test that empty lines in JSON Lines files are skipped"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"line": 1}\n')
            f.write('\n')  # Empty line
            f.write('{"line": 2}\n')
            f.write('   \n')  # Whitespace line
            f.write('{"line": 3}\n')
            temp_path = f.name
        
        try:
            data = load_json_or_jsonl(temp_path)
            assert data == [{"line": 1}, {"line": 2}, {"line": 3}]
        finally:
            Path(temp_path).unlink()
    
    def test_file_not_found(self) -> None:
        """Test that FileNotFoundError is raised for non-existent files"""
        with pytest.raises(FileNotFoundError):
            load_json_or_jsonl("/nonexistent/file.json")

from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def parse_version(version_str: str) -> tuple[int, int, int]:
    x_y_z = version_str.split(".")
    if len(x_y_z) != 3:
        raise ValueError(
            f"Invalid version format: {version_str}. Expected 'x.y.z' format."
        )

    x, y, z = map(int, x_y_z)  # Unpacking forces exactly 3 elements
    return (x, y, z)


def is_jsonl_file(file_path: str | Path) -> bool:
    """
    Determine if a file should be treated as JSON Lines based on its extension.
    
    Files with .jsonl extension are JSON Lines files.
    Files with .json extension ending with '_usage.json' are also JSON Lines (legacy).
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file should be treated as JSON Lines, False otherwise
    """
    path = Path(file_path)
    name = path.name
    
    # New standard: .jsonl extension
    if name.endswith('.jsonl'):
        return True
    
    # Legacy: _usage.json suffix (backward compatibility)
    if name.endswith('_usage.json') or name == 'usage.json':
        return True
    
    return False


def load_json_or_jsonl(file_path: str | Path) -> Any:
    """
    Load a file as either JSON or JSON Lines based on its extension and content.
    
    Args:
        file_path: Path to the file to load
        
    Returns:
        - For JSON files: the parsed JSON object/array
        - For JSON Lines files: a list of parsed JSON objects (one per line)
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON/JSONL
    """
    path = Path(file_path)
    
    if is_jsonl_file(path):
        # Load as JSON Lines (one JSON object per line)
        data = []
        with open(path, 'r') as file:
            for line in file:
                line = line.strip()
                if line:  # Skip empty lines
                    data.append(json.loads(line))
        return data
    else:
        # Load as regular JSON
        with open(path, 'r') as file:
            return json.load(file)

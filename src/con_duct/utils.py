def parse_version(version_str: str) -> tuple[int, int, int]:
    x_y_z = version_str.split(".")
    if len(x_y_z) != 3:
        raise ValueError(
            f"Invalid version format: {version_str}. Expected 'x.y.z' format."
        )

    x, y, z = map(int, x_y_z)  # Unpacking forces exactly 3 elements
    return (x, y, z)

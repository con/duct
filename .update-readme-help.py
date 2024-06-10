#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess

help_content = subprocess.run(
    ["duct", "--help"], check=True, text=True, encoding="utf-8", stdout=subprocess.PIPE
).stdout

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
text = re.sub(
    r"(?<=<!--- BEGIN HELP -->\n).*(?=^<!--- END HELP -->)",
    help_content,
    text,
    flags=re.S | re.M,
)
readme.write_text(text, encoding="utf-8")

#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess

help_content = subprocess.run(
    ["duct", "--help"], check=True, text=True, encoding="utf-8", stdout=subprocess.PIPE
).stdout

help_content = f"```shell\n>duct --help\n\n{help_content}\n```\n"

extras_help_content = subprocess.run(
    ["con-duct", "--help"],
    check=True,
    text=True,
    encoding="utf-8",
    stdout=subprocess.PIPE,
).stdout

extras_help_content = f"```shell\n>con-duct --help\n\n{extras_help_content}\n```\n"

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
text = re.sub(
    r"(?<=<!-- BEGIN HELP -->\n).*(?=^<!-- END HELP -->)",
    help_content,
    text,
    flags=re.S | re.M,
)

text = re.sub(
    r"(?<=<!-- BEGIN EXTRAS HELP -->\n).*(?=^<!-- END EXTRAS HELP -->)",
    extras_help_content,
    text,
    flags=re.S | re.M,
)

readme.write_text(text, encoding="utf-8")

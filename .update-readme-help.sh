#!/bin/bash
set -e
rm -f .help_content.txt
duct --help > .help_content.txt
sed -i '/<\!--- BEGIN HELP -->/,/<\!--- END HELP -->/{//!d;}' README.md
sed -i '/<\!--- BEGIN HELP -->/r .help_content.txt' README.md && rm -f .help_content.txt

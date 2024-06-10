#!/bin/bash
duct --help > .help_content.txt
sed -i '/<\!--- BEGIN HELP -->/,/<\!--- END HELP -->/{//!d;}' README.md
sed -i '/<\!--- BEGIN HELP -->/r .help_content.txt' README.md
rm .help_content.txt

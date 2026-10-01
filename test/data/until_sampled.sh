#!/bin/sh
# Stay alive until duct has recorded this process in its usage file, so a
# test can rely on at least one sample however slow the machine is.
# Usage: until_sampled.sh USAGE_FILE [TAG]
# TAG is unused; it only marks the command line so tests can find the process.
usage_file=$1
deadline=$(($(date +%s) + 60))
until grep -q "\"$$\"" "$usage_file" 2>/dev/null; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "until_sampled: pid $$ never appeared in $usage_file" >&2
        exit 1
    fi
    sleep 0.05
done

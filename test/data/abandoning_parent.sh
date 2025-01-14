#!/bin/bash

nchildren=$1
shift

for i in `seq 1 $nchildren`; do
	"$@" &
done

echo "Started $nchildren for $$"
# Can be useful when running manually, but commented out so we can count pids in tests
# pstree -c -p "$$"

echo "Starting one more in subprocess"

( "$@" & )

jobs

# Can be useful when running manually, but commented out so we can count pids in tests
# pstree -c -p "$$"
echo "waiting"
wait

#!/bin/bash

"$@" &

echo "Started one $$"
pstree -c -p "$$"

echo "Starting 2nd one in subprocess"

( "$@" & )

jobs

pstree -c -p "$$"
echo "waiting"
wait

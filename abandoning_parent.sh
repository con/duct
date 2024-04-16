#!/bin/bash

nchildren=$1
shift

for i in `seq 1 $nchildren`; do
	"$@" &
done

echo "Started $nchildren for $$"
pstree -c -p "$$"

echo "Starting one more in subprocess"

( "$@" & )

jobs

pstree -c -p "$$"
echo "waiting"
wait

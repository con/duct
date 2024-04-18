#!/bin/bash

nchildren=$1
shift

for i in `seq 1 $nchildren`; do
	"$@" &
done

echo "Started $nchildren for $$"
pstree -c -p "$$"

echo "Starting the same number in subprocesses"

for i in `seq 1 $nchildren`; do
	( "$@" & )
done

jobs

pstree -c -p "$$"
echo "waiting"
wait

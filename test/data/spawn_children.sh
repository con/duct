#!/bin/bash

mode=$1
nchildren=$2
shift 2

# Ensure at least one background process for `wait` to track
"$@" &

for i in $(seq 1 $nchildren); do
    case "$mode" in
        subshell)
            ( "$@" & ) ;;
        nohup)
            ( nohup "$@" & disown ) & ;;
        setsid)
            setsid "$@" & ;;
        plain)
            "$@" & ;;
        *)
            echo "Unknown mode: $mode" >&2
            exit 1
            ;;
    esac
done

wait

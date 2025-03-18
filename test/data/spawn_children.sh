#!/bin/bash

mode=$1
nchildren=$2
sleeptime=$3

# Ensure at least one background process for `wait` to track, we want this to take longer than the children.
long_sleep=$(awk "BEGIN {print $sleeptime * 1.5}")
sleep "$long_sleep" &

for _ in $(seq 1 "$nchildren"); do
    case "$mode" in
        subshell)
            ( sleep "$sleeptime" & ) ;;
        nohup)
            ( nohup sleep "$sleeptime" & disown ) & ;;
        setsid)
            setsid sleep "$sleeptime" & ;;
        plain)
            sleep "$sleeptime" & ;;
        *)
            echo "Unknown mode: $mode" >&2
            exit 1
            ;;
    esac
done

wait

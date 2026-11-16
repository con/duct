#!/bin/bash
# Spawn children in various ways, then exit once duct has had its chance to
# see them, so the test does not depend on how fast duct samples.
# Usage: spawn_children.sh MODE NCHILDREN USAGE_FILE STARTED_DIR
# Each child records its pid as a file in STARTED_DIR, so the test can tell
# exactly which pids to look for in the usage file.

mode=$1
nchildren=$2
usage_file=$3
started=$4
until_sampled="$(dirname "$0")/until_sampled.sh"

# Each child records its pid, then becomes until_sampled.sh (exec keeps the
# pid), so it stays alive until duct has recorded it.
child=(sh -c 'touch "$1/$$"; exec "$2" "$3"' _ "$started" "$until_sampled" "$usage_file")

# Give up after 60 s rather than hang if duct never samples.
deadline=$((SECONDS + 60))
wait_until() {
    until "$@"; do
        if [ "$SECONDS" -ge "$deadline" ]; then
            echo "spawn_children: timed out waiting for: $*" >&2
            exit 1
        fi
        sleep 0.05
    done
}
# $(( )) strips the padding macOS wc puts around its count
n_usage_lines() {
    if [ -f "$usage_file" ]; then echo $(($(wc -l < "$usage_file"))); else echo 0; fi
}

all_started() { [ $(($(find "$started" -type f | wc -l))) -ge "$nchildren" ]; }

case "$mode" in
    setsid)
        # Outside duct's session, so duct must not record these. The process
        # that calls setsid was forked inside duct's session and only then
        # left it, so duct may have sampled it. It therefore does not record
        # itself: it forks the child (the `; true` keeps sh from exec'ing it
        # in place), and that child was never in duct's session.
        for _ in $(seq 1 "$nchildren"); do
            setsid sh -c '"$@"; true' _ "${child[@]}" &
        done
        wait_until all_started
        # Two more reports, so duct has sampled while the children were alive
        target=$(($(n_usage_lines) + 2))
        reports_since_start() { [ "$(n_usage_lines)" -ge "$target" ]; }
        wait_until reports_since_start
        for f in "$started"/*; do
            kill "$(basename "$f")" 2>/dev/null
        done
        exit 0
        ;;
    subshell|nohup|plain) ;;
    *)
        echo "Unknown mode: $mode" >&2
        exit 1
        ;;
esac

for _ in $(seq 1 "$nchildren"); do
    case "$mode" in
        subshell)
            ( "${child[@]}" & ) ;;
        nohup)
            ( nohup "${child[@]}" & disown ) & ;;
        plain)
            "${child[@]}" & ;;
    esac
done

all_sampled() {
    for f in "$started"/*; do
        grep -q "\"$(basename "$f")\"" "$usage_file" 2>/dev/null || return 1
    done
}
wait_until all_started
wait_until all_sampled

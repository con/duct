#!/bin/bash

OUTPUT_FILE=/work2/03201/jbwexler/frontera/duct_test/duct_output.txt
COMMAND="datalad containers-run \
        --container-name containers/bids-mriqc \
        --input sourcedata \
        --output . \
        '{inputs}' '{outputs}' participant --participant-label sub-02 -w workdir"

rm "$OUTPUT_FILE"
$COMMAND &
# Get the process ID of the command and its child processes
PID=$(pgrep -d',' -P $$)

# Function to clean up and exit
cleanup_exit() {
    echo "Cleaning up..."
    kill $PID  # Kill the background process
    exit 0
}

# Trap Ctrl+C and call the cleanup function
trap 'cleanup_exit' INT

# Header for the output file
echo "Time  MemoryUsage(kB)  CPUUsage(%)" > $OUTPUT_FILE

# Monitor CPU and memory usage every 10 seconds
while ps -p $PID > /dev/null; do
    # Get the process IDs of the command and its child processes
    PIDS=$(pgrep -d',' -P $PID)
    
    TIME=$(date +"%Y-%m-%d %H:%M:%S")
    MEMORY_USAGE=$(top -p "$PIDS" -b -n 1 | awk 'NR>7 { sum += $6; } END { print sum; }')
    CPU_USAGE=$(top -p "$PIDS" -b -n 1 | awk 'NR>7 { sum += $9; } END { print sum; }')
    echo "$TIME  $MEMORY_USAGE  $CPU_USAGE" >> $OUTPUT_FILE
    sleep 1
done
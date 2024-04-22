#!/usr/bin/env python3

import subprocess
import sys
import time
import os
import argparse

def monitor_process(pid, elapsed_time, report_interval, process_data):
    """ Monitor and log basic details about the process. """
    try:
        # Check if the process is still running
        os.kill(pid, 0)
        # Aggregating data here, for demonstration we just record the event
        process_data.append(f"Process {pid} checked at {elapsed_time} seconds")
        if elapsed_time >= report_interval:
            print("\n".join(process_data))
            process_data.clear()
    except OSError:
        print(f"Process {pid} has terminated.")

def main(command, args, sample_interval, report_interval):
    """ A wrapper to execute a command, monitor and log the process details. """
    try:
        # Start the process
        print("Starting the command...")
        start_time = time.time()
        process = subprocess.Popen([command] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)

        process_data = []
        elapsed_time = 0

        # Monitor during execution
        try:
            while True:
                current_time = time.time()
                elapsed_time = current_time - start_time
                monitor_process(process.pid, elapsed_time, report_interval, process_data)
                if process.poll() is not None:
                    break
                time.sleep(sample_interval)  # Parameterized delay
        except KeyboardInterrupt:
            print("Monitoring interrupted.")

        # Collect outputs
        stdout, stderr = process.communicate()
        end_time = time.time()

        # Output results
        print(f"Command executed in {end_time - start_time:.2f} seconds.")
        print("STDOUT:", stdout.decode())
        print("STDERR:", stderr.decode())

    except Exception as e:
        print(f"Failed to execute command: {str(e)}")

if __name__ == "__main__":
    # Setup argparse to handle command line arguments
    parser = argparse.ArgumentParser(description="A process wrapper script that monitors the execution of a command.")
    parser.add_argument('command', help="The command to execute.")
    parser.add_argument('arguments', nargs='*', help="Arguments for the command.")
    parser.add_argument('--sample-interval', type=float, default=1.0, help="Interval in seconds between status checks of the running process.")
    parser.add_argument('--report-interval', type=float, default=60.0, help="Interval in seconds at which to report aggregated data.")

    args = parser.parse_args()

    main(args.command, args.arguments, args.sample_interval, args.report_interval)

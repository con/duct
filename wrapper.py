#!/usr/bin/env python3

import subprocess
import sys
import time
import os
import argparse

def monitor_process(pid):
    """ Monitor and log basic details about the process. """
    try:
        # Check if the process is still running
        os.kill(pid, 0)
        print(f"Process {pid} is still running.")
    except OSError:
        print(f"Process {pid} has terminated.")

def main(command, args, sample_interval):
    """ A wrapper to execute a command, monitor and log the process details. """
    try:
        # Start the process
        print("Starting the command...")
        start_time = time.time()
        process = subprocess.Popen([command] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Monitor during execution
        try:
            while True:
                monitor_process(process.pid)
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

    args = parser.parse_args()

    main(args.command, args.arguments, args.sample_interval)


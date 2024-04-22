#!/usr/bin/env python3

import subprocess
import sys
import time
import os


def monitor_process(pid):
    """ Monitor and log basic details about the process. """
    try:
        # Check if the process is still running
        os.kill(pid, 0)
        print(f"Process {pid} is still running.")
    except OSError:
        print(f"Process {pid} has terminated.")


def main(command, *args):
    """ A wrapper to execute a command, monitor and log the process details. """
    try:
        # Start the process
        print("Starting the command...")
        start_time = time.time()
        process = subprocess.Popen([command] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Monitor during execution
        try:
            while True:
                monitor_process(process.pid)
                if process.poll() is not None:
                    break
                time.sleep(1)  # Delay for a bit to avoid too much logging
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
    if len(sys.argv) > 1:
        main(sys.argv[1], *sys.argv[2:])
    else:
        print("Usage: wrapper <command> [arguments...]")

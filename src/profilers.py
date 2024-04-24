import subprocess
import os
import time
import json


def get_processes_in_session(session_id):
    """Retrieve all PIDs belonging to the given session ID."""
    pids = []
    for pid in os.listdir('/proc'):
        if pid.isdigit():
            try:
                with open(os.path.join('/proc', pid, 'stat'), 'r') as f:
                    data = f.read().split()
                if int(data[5]) == session_id:  # Check session ID in stat file
                    pids.append(int(pid))
            except IOError:  # proc has already terminated
                continue
    return pids


    
def pid_dummy_monitor(pid, elapsed_time, subreport):
    """A dummy function to simulate process monitoring and logging."""
    try:
        os.kill(pid, 0)  # Check if the process is still running
        subreport.pids_dummy[pid].append(f"Process {pid} checked at {elapsed_time} seconds")
    except OSError:
        subreport.pids_dummy[pid].append(f"Process {pid} has terminated.")

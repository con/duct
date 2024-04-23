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


def monitor_processes(session_id):
    """Monitor processes for the given session ID and collect resource usage metrics."""
    process_data = {}
    try:
        output = subprocess.check_output(["ps", "-s", str(session_id), "-o", "pid,pcpu,pmem,rss,vsz,etime,cmd"], text=True)
        for line in output.splitlines()[1:]:
            if line:
                pid, pcpu, pmem, rss, vsz, etime, cmd = line.split(maxsplit=6)
                process_data[pid] = {
                    'pcpu': float(pcpu),
                    'pmem': float(pmem),
                    'rss': int(rss),
                    'vsz': int(vsz),
                    'etime': etime,
                    'cmd': cmd
                }
    except subprocess.CalledProcessError:
        process_data['error'] = "Failed to query process data"

    return process_data

def pid_dummy_monitor(pid, elapsed_time, subreport):
    """A dummy function to simulate process monitoring and logging."""
    try:
        os.kill(pid, 0)  # Check if the process is still running
        subreport.pids_dummy[pid].append(f"Process {pid} checked at {elapsed_time} seconds")
    except OSError:
        subreport.pids_dummy[pid].append(f"Process {pid} has terminated.")



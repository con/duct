import os


def pid_dummy_monitor(pid, elapsed_time, subreport):
    try:
        os.kill(pid, 0)
        subreport.pids_dummy[pid].append(f"Process {pid} checked at {elapsed_time} seconds")
    except OSError:
        subreport.pids_dummy[pid].append(f"Process {pid} has terminated.")

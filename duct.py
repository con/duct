import os


def pid_dummy_monitor(pid, elapsed_time, report):
    try:
        os.kill(pid, 0)
        report["pids"][pid].append(f"Process {pid} checked at {elapsed_time} seconds")
    except OSError:
        report["pids"][pid].append(f"Process {pid} has terminated.")


def memory_total(elapsed_time, report):
    report["system"]["memory_total"] = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'),

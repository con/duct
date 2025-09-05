import argparse
from datetime import datetime
import json
import logging

lgr = logging.getLogger(__name__)


def matplotlib_plot(args: argparse.Namespace) -> int:
    try:
        import matplotlib
        from matplotlib.backends import backend_registry  # type: ignore[attr-defined]
        from matplotlib.backends.registry import BackendFilter
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as e:
        lgr.error("con-duct plot missing required dependency: %s", e)
        return 1

    # Handle info.json files by reading the usage path from the file
    file_path = args.file_path
    if file_path.endswith("info.json"):
        try:
            with open(file_path, "r") as info_file:
                info_data = json.load(info_file)
                file_path = info_data["output_paths"]["usage"]
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            lgr.error("Error reading info file %s: %s", args.file_path, e)
            return 1

    data = []
    try:
        with open(file_path, "r") as file:
            for line in file:
                data.append(json.loads(line))
    except FileNotFoundError:
        lgr.error("File %s was not found.", file_path)
        return 1
    except json.JSONDecodeError:
        lgr.error("File %s contained invalid JSON.", file_path)
        return 1

    try:
        # Convert timestamps to datetime objects
        timestamps = [datetime.fromisoformat(entry["timestamp"]) for entry in data]

        # Calculate elapsed time in seconds
        elapsed_time = np.array(
            [(ts - timestamps[0]).total_seconds() for ts in timestamps]
        )

        # Extract other data
        pmem = np.array([entry["totals"]["pmem"] for entry in data])
        pcpu = np.array([entry["totals"]["pcpu"] for entry in data])
        rss_kb = np.array([entry["totals"]["rss"] for entry in data])
        vsz_kb = np.array([entry["totals"]["vsz"] for entry in data])
    except KeyError as e:
        lgr.error("Usage file %s is missing required field: %s", file_path, e)
        return 1
    except ValueError as e:
        lgr.error("Usage file %s contains invalid data format: %s", file_path, e)
        return 1
    except Exception as e:
        lgr.error("Error processing usage file %s: %s", file_path, e)
        return 1

    # Plotting
    fig, ax1 = plt.subplots()

    # Plot pmem and pcpu on primary y-axis
    ax1.plot(elapsed_time, pmem, label="pmem (%)", color="tab:blue")
    ax1.plot(elapsed_time, pcpu, label="pcpu (%)", color="tab:orange")
    ax1.set_xlabel("Elapsed Time (s)")
    ax1.set_ylabel("Percentage")
    ax1.legend(loc="upper left")

    # Create a second y-axis for rss and vsz
    ax2 = ax1.twinx()  # type: ignore[attr-defined]
    ax2.plot(elapsed_time, rss_kb, label="rss (B)", color="tab:green")
    ax2.plot(elapsed_time, vsz_kb, label="vsz (B)", color="tab:red")
    ax2.set_ylabel("B")
    ax2.legend(loc="upper right")

    plt.title("Resource Usage Over Time")

    if args.output is not None:
        plt.savefig(args.output)
        lgr.info(
            "Successfully rendered input file: %s to output %s", file_path, args.output
        )
    else:
        # Check if the current backend can display plots interactively
        try:
            current_backend = matplotlib.get_backend()  # type: ignore[attr-defined]
        except AttributeError:
            # Fallback for matplotlib < 3.10
            current_backend = matplotlib.rcParams["backend"]  # type: ignore[attr-defined]
        interactive_backends = backend_registry.list_builtin(BackendFilter.INTERACTIVE)

        # Note: This only checks builtin backends. Custom interactive backends
        # would be incorrectly flagged as non-interactive. If this becomes an
        # issue, we could fallback to try/except around plt.show()
        if current_backend in interactive_backends:
            plt.show()
        else:
            lgr.error(
                "Cannot display plot: your current matplotlib backend is %s "
                "which is a not a known interactive backend.",
                current_backend,
            )
            lgr.error(
                "Either set environment variable MPLBACKEND to an interactive backend or "
                "use --output to save the plot to a file instead."
            )
            lgr.error(
                "For more info: https://matplotlib.org/stable/users/explain/figure/backends.html"
            )
            return 1

    # Exit code
    return 0

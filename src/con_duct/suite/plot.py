import argparse
from datetime import datetime
import json


def matplotlib_plot(args: argparse.Namespace) -> int:
    import matplotlib.pyplot as plt
    import numpy as np

    # Handle info.json files by reading the usage path from the file
    file_path = args.file_path
    if file_path.endswith("info.json"):
        try:
            with open(file_path, "r") as info_file:
                info_data = json.load(info_file)
                file_path = info_data["output_paths"]["usage"]
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            print(f"Error reading info file {args.file_path}: {e}")
            return 1

    data = []
    try:
        with open(file_path, "r") as file:
            for line in file:
                data.append(json.loads(line))
    except FileNotFoundError:
        print(f"File {file_path} was not found.")
        return 1
    except json.JSONDecodeError:
        print(f"File {file_path} contained invalid JSON.")
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
        print(f"Usage file {file_path} is missing required field: {e}")
        return 1
    except ValueError as e:
        print(f"Usage file {file_path} contains invalid data format: {e}")
        return 1
    except Exception as e:
        print(f"Error processing usage file {file_path}: {e}")
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
        print(f"Successfully rendered input file: {file_path} to output {args.output}")
    else:
        plt.show()

    # Exit code
    return 0

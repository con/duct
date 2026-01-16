import sys


def main() -> None:
    # Hardcoded number of interleaving iterations.
    n = 20

    for i in range(n):
        # Write to stdout then stderr, flushing each time to make interleaving visible.
        sys.stdout.write(f"stdout {i}\n")
        # sys.stdout.flush()

        # Tiny delay to make alternating output easier to observe in terminals/process capture.
        # time.sleep(0.01)

        sys.stderr.write(f"stderr {i}\n")
        # sys.stderr.flush()

        # time.sleep(0.01)


if __name__ == "__main__":
    main()

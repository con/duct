#!/usr/bin/env python3
import argparse
import sys


def cat_to_stream(path, buffer):
    with open(path, "rb") as infile:
        buffer.write(infile.read())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cat to stderr")
    parser.add_argument("path", help="Path to the file to be catted")
    args = parser.parse_args()
    cat_to_stream(args.path, sys.stderr.buffer)

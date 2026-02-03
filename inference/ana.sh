#!/bin/bash

# Usage examples:
# ./ana.sh /path/to/input/dir /path/to/output/dir
# ./ana.sh /path/to/input/dir  (output path defaults to parent directory of input path)
# ./ana.sh  (use default paths in script)

# Read command-line arguments
INPUT_DIR="${1:-}"
OUTPUT_DIR="${2:-}"

if [ -n "$INPUT_DIR" ] && [ -n "$OUTPUT_DIR" ]; then
    # Both input and output paths specified
    python ana_all_configs.py --input "$INPUT_DIR" --output "$OUTPUT_DIR"
elif [ -n "$INPUT_DIR" ]; then
    # Only input path specified
    python ana_all_configs.py --input "$INPUT_DIR"
else
    # Use default paths
    python ana_all_configs.py
fi

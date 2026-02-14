#!/bin/bash

# 使用示例:
# ./ana.sh /path/to/input/dir /path/to/output/dir
# ./ana.sh /path/to/input/dir  (输出路径默认为输入路径的父目录)
# ./ana.sh  (使用脚本中的默认路径)

# Read command-line arguments
INPUT_DIR="${1:-}"
OUTPUT_DIR="${2:-}"

if [ -n "$INPUT_DIR" ] && [ -n "$OUTPUT_DIR" ]; then
    # 同时指定输入和输出路径
    python ana_all_configs.py --input "$INPUT_DIR" --output "$OUTPUT_DIR"
elif [ -n "$INPUT_DIR" ]; then
    # 只指定输入路径
    python ana_all_configs.py --input "$INPUT_DIR"
else
    # 使用默认路径
    python ana_all_configs.py
fi

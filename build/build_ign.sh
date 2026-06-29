#!/usr/bin/env bash
#
# Script: build_fcos.sh
# Purpose: Compile Fedora CoreOS Butane configuration into an Ignition artifact.
# Requires: podman

set -e # Exit immediately if a command exits with a non-zero status

SOURCE_FILE="att-fcos-master.bu"
OUTPUT_FILE="att-fcos-master.ign"

# 1. Verify source existence
if [ ! -f "$SOURCE_FILE" ]; then
    echo "❌ Error: $SOURCE_FILE not found in $(pwd)."
    exit 1
fi

# 2. Execute compilation
echo "🚀 Compiling $SOURCE_FILE to $OUTPUT_FILE..."

podman run --rm -v "$(pwd):/pwd" -w /pwd quay.io/coreos/butane:release \
    --pretty --strict "$SOURCE_FILE" -o "$OUTPUT_FILE"

# 3. Final Verification
if [ -f "$OUTPUT_FILE" ]; then
    echo "✅ Success: $OUTPUT_FILE generated successfully."
else
    echo "❌ Error: Compilation failed to produce $OUTPUT_FILE."
    exit 1
fi

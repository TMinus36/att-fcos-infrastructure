#!/usr/bin/env bash
# Script: build/build_ign.sh
# Purpose: Compile Fedora CoreOS Butane configuration into an Ignition artifact.
# Execution: Agnostic (Can be run from project root or build/ directory)

set -e # Exit immediately if a command exits with a non-zero status

# Dynamically resolve the absolute path of the build/ directory
BUILD_DIR="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)"

SOURCE_FILE="${BUILD_DIR}/att-fcos-master.bu"
OUTPUT_FILE="${BUILD_DIR}/att-fcos-master.ign"

echo "============================================================"
echo "  [AUDIT] ATT Infrastructure - Ignition Compilation"
echo "============================================================"

# 1. Verify source existence
if [ ! -f "$SOURCE_FILE" ]; then
    echo "[ FAIL ] Error: Source configuration not found at $SOURCE_FILE."
    exit 1
fi

echo "[ INFO ] Compiling core configuration to Ignition artifact..."

# 2. Execute compilation via Podman
# Volume mounts strictly the BUILD_DIR to /pwd in the container
podman run --rm -v "${BUILD_DIR}:/pwd:z" -w /pwd quay.io/coreos/butane:release \
    --pretty --strict "att-fcos-master.bu" -o "att-fcos-master.ign"

# 3. Final Verification
if [ -f "$OUTPUT_FILE" ]; then
    echo "[  OK  ] Success: $OUTPUT_FILE generated successfully."
else
    echo "[ FAIL ] Error: Compilation failed to produce the artifact."
    exit 1
fi
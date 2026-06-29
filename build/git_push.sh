#!/usr/bin/env bash
# Script: build/git_push.sh
# Purpose: Stage, commit, and sync local configuration state with upstream remotes.

set -e

# Resolve the project root (one level up from the script's location)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." >/dev/null 2>&1 && pwd)"

echo "============================================================"
echo "  [AUDIT] ATT GitOps - Pipeline Synchronization"
echo "============================================================"

# Check if a commit message was provided as an argument
if [ -z "$1" ]; then
  echo "[ FAIL ] Error: No commit message provided."
  echo "Usage: ./build/git_push.sh \"Your commit message here\""
  exit 1
fi

COMMIT_MESSAGE="$1"

# Force shell context to the root of the repository
cd "$PROJECT_ROOT"

echo "[ INFO ] Evaluating git status..."
git status -s

echo "[ INFO ] Adding files to staging..."
git add .

echo "[ INFO ] Committing configuration state..."
git commit -m "$COMMIT_MESSAGE"

echo "[ INFO ] Pushing to remote GitOps repository..."
git push origin main

echo "[  OK  ] Synchronization complete! Pipeline triggered."
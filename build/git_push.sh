#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Check if a commit message was provided as an argument
if [ -z "$1" ]; then
  echo "Error: No commit message provided."
  echo "Usage: ./git_push.sh \"Your commit message here\""
  exit 1
fi

COMMIT_MESSAGE=$1

echo "Checking git status..."
git status -s

echo "Adding files to staging..."
git add .

echo "Committing with message: '$COMMIT_MESSAGE'..."
git commit -m "$COMMIT_MESSAGE"

echo "Pushing to remote repository..."
# Assuming you are pushing to the 'main' branch. Change to 'master' if needed.
git push origin main

echo "Push complete!"
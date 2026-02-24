#!/bin/bash
set -e

# Usage: ./scripts/switch_env.sh <env>
# where <env> is 'local', 'dev', or 'prd'

ENV_NAME=${1:-"local"}
ENV_FILE=".env.${ENV_NAME}"
SYMLINK=".env"

echo "Switching to environment: $ENV_NAME"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE does not exist."
  echo "Run './scripts/generate_env.sh $ENV_NAME' first."
  exit 1
fi

# Remove existing .env (whether it's a file or symlink)
if [ -e "$SYMLINK" ] || [ -L "$SYMLINK" ]; then
  rm -f "$SYMLINK"
fi

# Create symlink
ln -s "$ENV_FILE" "$SYMLINK"

echo "Environment switched to $ENV_NAME"
echo "Current $SYMLINK -> $ENV_FILE"

# Show current configuration
echo ""
echo "Current configuration:"
cat $SYMLINK

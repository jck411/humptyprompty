#!/bin/bash

# Script to set up the NEW virtual environment with only backend requirements

SETUP_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_PATH="$(dirname "$SETUP_DIR")"
VENV_PATH="$PROJECT_PATH/venv"

echo "Setting up backend environment at $VENV_PATH..."

# Check if virtual environment exists, create if it doesn't
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating new virtual environment..."
    python -m venv "$VENV_PATH"
fi

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

echo "Installing common requirements..."
pip install -r "$SETUP_DIR/requirements-common.txt"

echo "Installing backend requirements..."
pip install -r "$SETUP_DIR/requirements-backend.txt"

# Ensure critical backend dependencies are installed
echo "Ensuring critical backend dependencies are installed..."
pip install requests==2.32.3 pytz==2025.1 timezonefinder==6.5.8

echo "Backend environment setup complete!"
echo "To activate the virtual environment, run:"
echo "source $VENV_PATH/bin/activate"
echo ""
echo "You can now run the backend application." 
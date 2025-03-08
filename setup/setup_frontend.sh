#!/bin/bash

# Script to set up the NEW virtual environment with only frontend requirements

SETUP_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_PATH="$(dirname "$SETUP_DIR")"
VENV_PATH="$PROJECT_PATH/venv"

echo "Setting up frontend environment at $VENV_PATH..."

# Check if virtual environment exists, create if it doesn't
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating new virtual environment..."
    python -m venv "$VENV_PATH"
fi

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

echo "Installing common requirements..."
pip install -r "$SETUP_DIR/requirements-common.txt"

echo "Installing frontend requirements..."
pip install -r "$SETUP_DIR/requirements-frontend.txt"

echo "Frontend environment setup complete!"
echo "To activate the virtual environment, run:"
echo "source $VENV_PATH/bin/activate"
echo ""
echo "You can now run the frontend application." 
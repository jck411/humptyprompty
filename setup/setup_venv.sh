#!/bin/bash

# Script to set up the NEW virtual environment with required packages

SETUP_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_PATH="$(dirname "$SETUP_DIR")"
VENV_PATH="$PROJECT_PATH/venv"

echo "Setting up virtual environment at $VENV_PATH..."

# Check if virtual environment exists, create if it doesn't
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating new virtual environment..."
    python -m venv "$VENV_PATH"
fi

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

echo "Installing common requirements..."
pip install -r "$SETUP_DIR/requirements-common.txt"

echo "Do you want to install frontend requirements? (y/n)"
read -r install_frontend
if [[ "$install_frontend" == "y" ]]; then
    echo "Installing frontend requirements..."
    pip install -r "$SETUP_DIR/requirements-frontend.txt"
fi

echo "Do you want to install backend requirements? (y/n)"
read -r install_backend
if [[ "$install_backend" == "y" ]]; then
    echo "Installing backend requirements..."
    pip install -r "$SETUP_DIR/requirements-backend.txt"
    
    # Ensure critical backend dependencies are installed
    echo "Ensuring critical backend dependencies are installed..."
    pip install requests==2.32.3 pytz==2025.1 timezonefinder==6.5.8
fi

echo "Virtual environment setup complete!"
echo "To activate the virtual environment, run:"
echo "source $VENV_PATH/bin/activate" 
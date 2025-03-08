#!/bin/bash

# Main setup script that provides options to run any of the setup scripts

SETUP_DIR="$(dirname "$(readlink -f "$0")")/setup"
PROJECT_PATH="$(dirname "$(readlink -f "$0")")"
VENV_PATH="$PROJECT_PATH/venv"

echo "===== Virtual Environment Setup ====="
echo "This will create a virtual environment in: $VENV_PATH"
echo "Please select an option:"
echo "1. Full setup (frontend and backend)"
echo "2. Frontend only"
echo "3. Backend only"
echo "4. Exit"
echo ""

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo "Running full setup..."
        bash "$SETUP_DIR/setup_venv.sh"
        ;;
    2)
        echo "Running frontend setup..."
        bash "$SETUP_DIR/setup_frontend.sh"
        ;;
    3)
        echo "Running backend setup..."
        bash "$SETUP_DIR/setup_backend.sh"
        ;;
    4)
        echo "Exiting setup."
        exit 0
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo "Setup completed!"
echo "To activate the virtual environment, run:"
echo "source $VENV_PATH/bin/activate" 
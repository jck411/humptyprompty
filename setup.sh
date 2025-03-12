#!/bin/bash

# Define directories
PROJECT_PATH="$(dirname "$(readlink -f "$0")")"
REQ_DIR="$PROJECT_PATH/requirements"
DEFAULT_VENV_PATH="$PROJECT_PATH/venv"

# Clear screen and show header
clear
echo "========================================================"
echo "          HumptyPrompty Project Setup"
echo "========================================================"

# Function to check and install system dependencies
install_system_dependencies() {
    echo -e "\n=== CHECKING SYSTEM DEPENDENCIES ==="
    
    # Check if we're on a Debian/Ubuntu system
    if command -v apt-get &> /dev/null; then
        echo "Installing required system packages for PyAudio..."
        sudo apt-get update -qq
        sudo apt-get install -y portaudio19-dev python3-dev build-essential
        echo "System dependencies installed."
    else
        echo "Non-Debian/Ubuntu system detected. Please install PortAudio development package manually if needed."
    fi
}

# Function to install packages directly into a virtual environment
install_to_venv() {
    local venv_path=$1
    local req_file=$2
    
    echo "Installing packages from $req_file into $venv_path..."
    # First upgrade pip
    "$venv_path/bin/pip" install --upgrade pip
    
    # Check if PyAudio is in the requirements and already installed
    if grep -q "PyAudio" "$req_file" && "$venv_path/bin/pip" show PyAudio &> /dev/null; then
        echo "PyAudio is already installed. Skipping PyAudio installation."
        # Install all non-PyAudio packages
        grep -v "PyAudio" "$req_file" > "$req_file.temp"
        "$venv_path/bin/pip" install -r "$req_file.temp"
        rm "$req_file.temp"
    elif grep -q "PyAudio" "$req_file"; then
        # Install all non-PyAudio packages first
        grep -v "PyAudio" "$req_file" > "$req_file.temp"
        "$venv_path/bin/pip" install -r "$req_file.temp"
        rm "$req_file.temp"
        
        # Install PyAudio with special handling
        echo "Installing PyAudio..."
        export CFLAGS="-I/usr/include -I/usr/local/include"
        
        # Check for portaudio.h in more locations
        for dir in /usr/include /usr/local/include /usr/include/*/; do
            if [ -f "${dir}portaudio.h" ]; then
                export CFLAGS="$CFLAGS -I${dir}"
                break
            fi
        done
        
        # Try using pkg-config if available
        if command -v pkg-config &> /dev/null && pkg-config --exists portaudio-2.0; then
            export CFLAGS="$CFLAGS $(pkg-config --cflags portaudio-2.0)"
            export LDFLAGS="$(pkg-config --libs portaudio-2.0)"
        fi
        
        # Install PyAudio
        "$venv_path/bin/pip" install --no-cache-dir --force-reinstall PyAudio || 
            echo "Warning: PyAudio installation failed. Install system package portaudio19-dev and try again."
    else
        # Install all packages normally
        "$venv_path/bin/pip" install -r "$req_file"
    fi
}

# Virtual environment setup
echo -e "\n=== VIRTUAL ENVIRONMENT SETUP ==="

# Check if a virtual environment is already active
if [ -n "$VIRTUAL_ENV" ]; then
    echo "* Active virtual environment detected: $VIRTUAL_ENV"
    echo "Select an option:"
    echo "  1) Use this active virtual environment"
    echo "  2) Use a different existing virtual environment"
    echo "  3) Create a new virtual environment"
    echo "  4) Exit"
    
    read -p "Choice [1-4]: " venv_choice
    
    case $venv_choice in
        1)
            VENV_PATH="$VIRTUAL_ENV"
            CREATE_NEW_VENV=false
            echo "Using active virtual environment: $VENV_PATH"
            ;;
        2)
            read -p "Enter path to existing virtual environment: " VENV_PATH
            if [ ! -d "$VENV_PATH" ] || [ ! -f "$VENV_PATH/bin/activate" ]; then
                echo "ERROR: Invalid virtual environment path."
                exit 1
            fi
            CREATE_NEW_VENV=false
            ;;
        3)
            read -p "Use default location ($DEFAULT_VENV_PATH)? [Y/n]: " use_default
            if [[ "$use_default" =~ ^[nN]$ ]]; then
                read -p "Enter path for new virtual environment: " VENV_PATH
            else
                VENV_PATH="$DEFAULT_VENV_PATH"
            fi
            CREATE_NEW_VENV=true
            ;;
        4|*)
            echo "Exiting setup."
            exit 0
            ;;
    esac
else
    echo "Select an option:"
    echo "  1) Use an existing virtual environment"
    echo "  2) Create a new virtual environment"
    echo "  3) Exit"
    
    read -p "Choice [1-3]: " venv_choice
    
    case $venv_choice in
        1)
            read -p "Enter path to existing virtual environment: " VENV_PATH
            if [ ! -d "$VENV_PATH" ] || [ ! -f "$VENV_PATH/bin/activate" ]; then
                echo "ERROR: Invalid virtual environment path."
                exit 1
            fi
            CREATE_NEW_VENV=false
            ;;
        2)
            read -p "Use default location ($DEFAULT_VENV_PATH)? [Y/n]: " use_default
            if [[ "$use_default" =~ ^[nN]$ ]]; then
                read -p "Enter path for new virtual environment: " VENV_PATH
            else
                VENV_PATH="$DEFAULT_VENV_PATH"
            fi
            CREATE_NEW_VENV=true
            ;;
        3|*)
            echo "Exiting setup."
            exit 0
            ;;
    esac
fi

# Before installing packages, check and install system dependencies
install_system_dependencies

# Create virtual environment if needed
if [ "$CREATE_NEW_VENV" = true ]; then
    echo -e "\n=== CREATING VIRTUAL ENVIRONMENT ==="
    if [ -d "$VENV_PATH" ]; then
        echo "Removing existing virtual environment..."
        rm -rf "$VENV_PATH"
    fi
    
    echo "Creating new virtual environment at: $VENV_PATH"
    python3 -m venv "$VENV_PATH"
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment."
        exit 1
    fi
fi

# Setup options
echo -e "\n=== PROJECT SETUP OPTIONS ==="
echo "Select components to set up:"
echo "  1) Full setup (frontend and backend)"
echo "  2) Frontend only"
echo "  3) Backend only"
echo "  4) Exit"

read -p "Choice [1-4]: " setup_choice

case $setup_choice in
    1)
        echo -e "\n=== INSTALLING COMMON REQUIREMENTS ==="
        install_to_venv "$VENV_PATH" "$REQ_DIR/requirements-common.txt"
        
        echo -e "\n=== INSTALLING FRONTEND REQUIREMENTS ==="
        install_to_venv "$VENV_PATH" "$REQ_DIR/requirements-frontend.txt"
        
        echo -e "\n=== INSTALLING BACKEND REQUIREMENTS ==="
        install_to_venv "$VENV_PATH" "$REQ_DIR/requirements-backend.txt"
        # Any backend-specific setup that doesn't involve creating a venv
        ;;
    2)
        echo -e "\n=== INSTALLING COMMON REQUIREMENTS ==="
        install_to_venv "$VENV_PATH" "$REQ_DIR/requirements-common.txt"
        
        echo -e "\n=== INSTALLING FRONTEND REQUIREMENTS ==="
        install_to_venv "$VENV_PATH" "$REQ_DIR/requirements-frontend.txt"
        # Any frontend-specific setup that doesn't involve creating a venv
        ;;
    3)
        echo -e "\n=== INSTALLING COMMON REQUIREMENTS ==="
        install_to_venv "$VENV_PATH" "$REQ_DIR/requirements-common.txt"
        
        echo -e "\n=== INSTALLING BACKEND REQUIREMENTS ==="
        install_to_venv "$VENV_PATH" "$REQ_DIR/requirements-backend.txt"
        # Any backend-specific setup that doesn't involve creating a venv
        ;;
    4|*)
        echo "Exiting setup."
        exit 0
        ;;
esac

echo -e "\n========================================================"
echo "Setup completed successfully!"
echo -e "Virtual environment: $VENV_PATH"
echo "To activate this virtual environment, run:"
echo "    source $VENV_PATH/bin/activate"
echo "========================================================"
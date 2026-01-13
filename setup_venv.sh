#!/bin/bash
# Setup script for virtual environment

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

echo "Virtual environment created and activated!"
echo "To activate in the future, run: source venv/bin/activate"


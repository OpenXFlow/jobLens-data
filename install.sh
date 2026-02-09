#!/bin/bash

# jobLens Project - Automated Installer
# This script sets up the directory structure and installs dependencies.
# Usage: bash install.sh

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          jobLens - Project Setup & Installer                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 1. Python Environment Check
echo "🐍 1. Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed!"
    exit 1
fi
echo "✓ Python detected."

# 2. Dependency Installation
echo "📦 2. Installing project dependencies..."
if [ -f "pyproject.toml" ]; then
    # Modern approach using PEP 517/518
    python3 -m pip install --upgrade pip
    python3 -m pip install .
    echo "✓ Dependencies installed via pyproject.toml"
elif [ -f "requirements.txt" ]; then
    python3 -m pip install -r requirements.txt
    echo "✓ Dependencies installed via requirements.txt"
else
    echo "⚠️  Warning: No pyproject.toml or requirements.txt found. Skipping installation."
fi

# 3. Directory Structure Initialization
echo "📁 3. Initializing directory structure..."
mkdir -p outputs results logs configs/core configs/data configs/search_profiles configs/my_profile src/core src/cli src/utils
echo "✓ Directories created."

# 4. Profile Template Setup
echo "👤 4. Setting up configuration templates..."
if [ ! -f "configs/my_profile/my_profile.json" ] && [ -f "configs/my_profile/my_profile.json.example" ]; then
    cp configs/my_profile/my_profile.json.example configs/my_profile/my_profile.json
    echo "✓ Local profile created from template."
fi

# 5. Permission Configuration
echo "🔧 5. Setting file permissions..."
chmod +x install.sh 2>/dev/null || true
if [ -f "jobLens.py" ]; then
    chmod +x jobLens.py 2>/dev/null || true
fi
echo "✓ Permissions configured."

echo ""
echo "✅ INSTALLATION COMPLETE!"
echo "🚀 You can now run the agent using: python3 jobLens.py"
echo ""

# End of install.sh (v. 00002)

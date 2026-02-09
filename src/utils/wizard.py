# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida
# LinkedIn Job Searcher Project

"""JobLens Setup Wizard.

Interactive script for project initialization and directory structure creation.
This script is designed to be run from the project root or directly from the utils folder.
python -m src.utils.wizard
python src/utils/wizard.py
"""

import shutil
from pathlib import Path
from typing import List


def get_project_root() -> Path:
    """Calculates the project root directory based on this script's location.

    Returns:
        Path: The absolute path to the project root.
    """
    # src/utils/wizard.py -> parents[0]=utils, parents[1]=src, parents[2]=root
    return Path(__file__).resolve().parents[2]


# --- CONFIGURATION ---
PROJECT_ROOT: Path = get_project_root()

PROJECT_DIRS: List[str] = [
    "outputs",
    "logs",
    "configs/core",
    "configs/data",
    "configs/search_profiles",
    "configs/my_profile",
    "src/core",
    "src/cli",
    "src/utils",
    "src/core/providers",
]


def print_step(step: int, msg: str) -> None:
    """Prints a formatted step message to the console.

    Args:
        step: The step number.
        msg: The message to display.
    """
    print(f"\n[Step {step}/2] {msg}")
    print("-" * 50)


def create_structure() -> None:
    """Creates the necessary directory structure for the project."""
    print_step(1, "Creating directory structure")
    for d in PROJECT_DIRS:
        # Resolve path relative to the calculated project root
        path = PROJECT_ROOT / d
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"   📁 Created: {d}/")
        else:
            print(f"   ✓ Exists: {d}/")


def setup_profile() -> None:
    """Sets up the user profile configuration file from example if needed."""
    print_step(2, "Profile Initialization")

    profile_dir = PROJECT_ROOT / "configs/my_profile"
    target = profile_dir / "my_profile.json"
    example = profile_dir / "my_profile.json.example"

    # Fallback for older versions or root location
    root_example = PROJECT_ROOT / "my_profile.json.example"

    if not example.exists() and root_example.exists():
        example = root_example

    if target.exists():
        print("   ✅ Profile already exists (skipping).")
    elif example.exists():
        shutil.copy(example, target)
        print("   ✅ Created new profile from template.")
    else:
        print(f"   ⚠️ Profile template not found at {example}.")


def main() -> None:
    """Main execution function for the setup wizard."""
    print(r"""
    🛠️  JobLens Wizard
    """)
    try:
        print(f"   📍 Project Root detected: {PROJECT_ROOT}")
        create_structure()
        setup_profile()
        print("\n✅ Done! You can now run: python jobLens.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()

# End of src/utils/wizard.py (v. 3.3.0)

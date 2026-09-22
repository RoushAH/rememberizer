"""Initialize the database with tables and sample data."""

import os
import sys

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# E402: has to follow the sys.path setup above to import at all
from app import app, init_database  # noqa: E402


def main():
    """Initialize the database."""
    print("\nInitializing database...")
    from app import DB_PATH

    print(f"Database location: {DB_PATH}")

    # Set testing flag to skip interactive prompts
    app.config["TESTING"] = True

    # Initialize the database
    init_database()

    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    main()

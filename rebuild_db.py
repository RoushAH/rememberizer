"""Completely rebuild the database from scratch."""

import os
import sys
import sqlite3
import time

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "instance", "database.db"
)


def rebuild_database():
    """Delete and rebuild database from scratch."""
    print("\n" + "=" * 60)
    print("DATABASE REBUILD FROM SCRATCH")
    print("=" * 60)

    # Step 1: Check if database exists
    if os.path.exists(DB_PATH):
        print(f"\n1. Found existing database at: {DB_PATH}")
        print(f"   Size: {os.path.getsize(DB_PATH)} bytes")

        # Close any existing connections
        print("\n2. Closing any existing connections...")
        try:
            # Force close by connecting and immediately closing
            conn = sqlite3.connect(DB_PATH)
            conn.close()
            time.sleep(0.5)  # Give OS time to release file
        except Exception:
            # Best effort only - the delete below reports the real failure
            pass

        # Delete the file
        print("\n3. Deleting database file...")
        try:
            os.remove(DB_PATH)
            print("   [OK] Database file deleted")
        except Exception as e:
            print(f"   [ERROR] Could not delete database: {e}")
            print(
                "\n   Please close any programs that might be accessing the database:"
            )
            print("   - Flask development server")
            print("   - DB Browser for SQLite")
            print("   - Python shells/scripts")
            return False
    else:
        print(f"\n1. No existing database found at: {DB_PATH}")

    # Step 2: Initialize fresh database
    print("\n4. Creating fresh database...")

    from app import app, db

    # FactState, Attempt and UserDomainAssignment are imported for their side
    # effect: every model must be registered before db.create_all() to get a table.
    from models import (  # noqa: F401
        Domain,
        Fact,
        User,
        Organization,
        FactState,
        Attempt,
        UserDomainAssignment,
    )
    from facts_loader import load_all_domains_from_directory

    with app.app_context():
        # Create all tables
        print("   Creating tables...")
        db.create_all()

        # Create default organization
        print("   Creating default organization...")
        org = Organization(id=1, name="Default Organization")
        db.session.add(org)
        db.session.commit()

        # Load fact domains
        print("   Loading fact domains from 'facts' directory...")
        domains_loaded = load_all_domains_from_directory("facts")
        print(f"   Loaded {domains_loaded} domains")

        # Verify
        print("\n5. Verifying database...")
        print(f"   - Organizations: {Organization.query.count()}")
        print(f"   - Domains: {Domain.query.count()}")
        print(f"   - Facts: {Fact.query.count()}")
        print(f"   - Users: {User.query.count()}")

    print("\n" + "=" * 60)
    print("[SUCCESS] Database rebuilt successfully!")
    print("=" * 60)
    print("\nYou can now:")
    print("1. Run the app: python app.py")
    print("2. Create an admin account when prompted")
    print("3. Test that data persists between restarts")
    print()

    return True


if __name__ == "__main__":
    success = rebuild_database()
    sys.exit(0 if success else 1)

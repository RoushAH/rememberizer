"""Force database initialization with detailed error reporting."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# E402: these have to follow the sys.path setup above to import at all
from app import app, db, DB_PATH  # noqa: E402
from models import (  # noqa: E402
    Domain,
    Fact,
    User,
    Organization,
    FactState,
    Attempt,
    UserDomainAssignment,
)


def force_init():
    """Force initialize database with error checking."""
    print(f"\nDatabase path: {DB_PATH}")
    print(f"Database file exists: {os.path.exists(DB_PATH)}")
    print(f"Database file size: {os.path.getsize(DB_PATH)} bytes")

    with app.app_context():
        try:
            print("\n1. Dropping all existing tables...")
            db.drop_all()
            print("   [OK] Tables dropped")

            print("\n2. Creating all tables...")
            db.create_all()
            print("   [OK] Tables created")

            print("\n3. Committing changes...")
            db.session.commit()
            print("   [OK] Changes committed")

            print("\n4. Verifying tables...")
            # Try to query each model
            print(f"   - Organizations: {Organization.query.count()}")
            print(f"   - Users: {User.query.count()}")
            print(f"   - Domains: {Domain.query.count()}")
            print(f"   - Facts: {Fact.query.count()}")
            print(f"   - FactStates: {FactState.query.count()}")
            print(f"   - Attempts: {Attempt.query.count()}")
            print(f"   - UserDomainAssignments: {UserDomainAssignment.query.count()}")

            print("\n[SUCCESS] Database initialized successfully!")
            return True

        except Exception as e:
            print(f"\n[ERROR] Error during initialization: {e}")
            import traceback

            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = force_init()
    sys.exit(0 if success else 1)

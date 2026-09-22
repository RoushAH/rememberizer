"""Verify database configuration and persistence."""

import os
import sys
from datetime import datetime

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# E402: these have to follow the sys.path setup above to import at all
from app import app, DB_PATH  # noqa: E402
from models import Domain, User, UserDomainAssignment  # noqa: E402


def verify_database():
    """Verify database location and content."""
    print("\n" + "=" * 70)
    print("DATABASE VERIFICATION")
    print("=" * 70)

    # Show configured path
    print("\n[OK] Database configured at:")
    print(f"  {DB_PATH}")

    # Check if file exists
    if os.path.exists(DB_PATH):
        # Get file size and modification time
        file_size = os.path.getsize(DB_PATH)
        file_mtime = datetime.fromtimestamp(os.path.getmtime(DB_PATH))

        print("\n[OK] Database file exists:")
        print(f"  Size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
        print(f"  Last modified: {file_mtime.strftime('%Y-%m-%d %H:%M:%S')}")

        # Query database content
        with app.app_context():
            try:
                domain_count = Domain.query.count()
                user_count = User.query.count()
                assignment_count = UserDomainAssignment.query.count()

                print("\n[OK] Database contains:")
                print(f"  Domains: {domain_count}")
                print(f"  Users: {user_count}")
                print(f"  Domain assignments: {assignment_count}")

                # Show some sample data
                if user_count > 0:
                    print("\n[OK] Sample users:")
                    users = User.query.limit(5).all()
                    for user in users:
                        print(f"  - {user.email} ({user.role})")

                if domain_count > 0:
                    print("\n[OK] Sample domains:")
                    domains = Domain.query.limit(5).all()
                    for domain in domains:
                        visibility = (
                            "published" if domain.is_published else "unpublished"
                        )
                        print(f"  - {domain.name} ({visibility})")

                print("\n" + "=" * 70)
                print("[SUCCESS] DATABASE IS CORRECTLY CONFIGURED AND CONTAINS DATA")
                print("=" * 70 + "\n")

                return True

            except Exception as e:
                print(f"\n[ERROR] Error querying database: {e}")
                return False
    else:
        print(f"\n[ERROR] Database file does not exist at: {DB_PATH}")
        print("\nThis is expected on first run. Start the app to create it.")
        return False


if __name__ == "__main__":
    verify_database()

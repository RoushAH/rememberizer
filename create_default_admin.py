"""Create a default admin user (non-interactive)."""

import sys
from app import app, db
from models import User, Organization
from services.user_service import create_user

def create_default_admin():
    """Create a default admin user."""
    print("\n" + "="*60)
    print("CREATING DEFAULT ADMIN ACCOUNT")
    print("="*60)

    with app.app_context():
        # Check if admin already exists
        existing_admin = User.query.filter_by(role="admin").first()
        if existing_admin:
            print(f"\nAdmin account already exists:")
            print(f"  Email: {existing_admin.email}")
            print(f"  Name: {existing_admin.get_full_name()}")
            print("\nIf you forgot your password, you can reset it by:")
            print("  1. Deleting the database and rebuilding")
            print("  2. Or manually updating the password_hash in the database")
            return False

        # Get or create default organization
        org = Organization.query.first()
        if not org:
            org = Organization(id=1, name="Default Organization")
            db.session.add(org)
            db.session.commit()

        try:
            # Create default admin user
            admin = create_user(
                email="admin@admin.admin",
                password="adminpass123",  # Default password
                role="admin",
                first_name="Admin",
                last_name="User",
                organization_id=org.id
            )
            db.session.commit()

            print("\n" + "="*60)
            print("SUCCESS! Default admin account created.")
            print("="*60)
            print(f"\nEmail:    admin@admin.admin")
            print(f"Password: adminpass123")
            print(f"Name:     {admin.get_full_name()}")
            print(f"Role:     {admin.role}")
            print(f"\n*** IMPORTANT: Change this password after first login! ***")
            print(f"\nYou can now log in at: http://127.0.0.1:5000/login")
            print()

            return True

        except ValueError as e:
            print(f"\nError: {e}")
            return False

if __name__ == "__main__":
    success = create_default_admin()
    sys.exit(0 if success else 1)

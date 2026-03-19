"""Create an admin user for the Rememberizer app."""

import sys
import getpass
from app import app, db
from models import User, Organization
from services.user_service import create_user

def create_admin():
    """Create an admin user interactively."""
    print("\n" + "="*60)
    print("CREATE ADMIN ACCOUNT")
    print("="*60)

    with app.app_context():
        # Check if admin already exists
        existing_admin = User.query.filter_by(role="admin").first()
        if existing_admin:
            print(f"\nAdmin account already exists: {existing_admin.email}")
            response = input("\nDo you want to create another admin? [y/N]: ").strip().lower()
            if response not in ["y", "yes"]:
                print("Cancelled.")
                return False

        # Get admin details
        print("\nEnter admin account details:")
        print("-" * 60)

        email = input("Email [admin@admin.admin]: ").strip() or "admin@admin.admin"
        first_name = input("First name [Admin]: ").strip() or "Admin"
        last_name = input("Last name [User]: ").strip() or "User"

        # Get password with confirmation
        while True:
            password = getpass.getpass("Password (min 8 characters): ").strip()
            if len(password) < 8:
                print("Password must be at least 8 characters long. Try again.")
                continue

            password_confirm = getpass.getpass("Confirm password: ").strip()
            if password != password_confirm:
                print("Passwords don't match. Try again.")
                continue

            break

        # Get or create default organization
        org = Organization.query.first()
        if not org:
            org = Organization(id=1, name="Default Organization")
            db.session.add(org)
            db.session.commit()

        try:
            # Create admin user
            admin = create_user(
                email=email,
                password=password,
                role="admin",
                first_name=first_name,
                last_name=last_name,
                organization_id=org.id
            )
            db.session.commit()

            print("\n" + "="*60)
            print("SUCCESS! Admin account created.")
            print("="*60)
            print(f"\nEmail: {admin.email}")
            print(f"Name: {admin.get_full_name()}")
            print(f"Role: {admin.role}")
            print(f"\nYou can now log in at: http://127.0.0.1:5000/login")
            print()

            return True

        except ValueError as e:
            print(f"\nError: {e}")
            return False

if __name__ == "__main__":
    success = create_admin()
    sys.exit(0 if success else 1)

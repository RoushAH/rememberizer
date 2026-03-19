"""Test database persistence across multiple Python sessions."""

import os
import sys
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_in_separate_process(code):
    """Run Python code in a completely separate process."""
    result = subprocess.run(
        ["python", "-c", code],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True
    )
    return result.stdout, result.returncode

def test_persistence():
    """Test that data persists across separate Python processes."""
    print("\n" + "="*60)
    print("PERSISTENCE TEST")
    print("="*60)

    # Step 0: Clean up any existing test user
    print("\n0. Cleanup: Removing any existing test user...")
    code0 = """
from app import app, db
from models import User

with app.app_context():
    user = User.query.filter_by(email="persistence_test@test.com").first()
    if user:
        db.session.delete(user)
        db.session.commit()
        print("Removed existing test user")
    else:
        print("No existing test user found")
"""
    output0, _ = run_in_separate_process(code0)
    print(output0.strip())

    time.sleep(1)

    # Step 1: Create a test user in process #1
    print("\n1. Process #1: Creating test user...")
    code1 = """
from app import app, db
from models import User, Organization
from services.user_service import create_user

with app.app_context():
    # Create test user
    org = Organization.query.first()
    user = create_user(
        email="persistence_test@test.com",
        password="testpass123",
        role="student",
        first_name="Persistence",
        last_name="Test",
        organization_id=org.id
    )
    db.session.commit()
    print(f"Created user: {user.email}")
    print(f"User ID: {user.id}")
"""
    output1, code = run_in_separate_process(code1)
    print(output1.strip())
    if code != 0:
        print("   [FAILED] Could not create user")
        # Show stderr for debugging
        result = subprocess.run(
            ["python", "-c", code1],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True
        )
        print("   Error output:", result.stderr)
        return False

    time.sleep(1)  # Brief pause to ensure file writes are flushed

    # Step 2: Query for the user in process #2 (completely new Python instance)
    print("\n2. Process #2: Querying for test user...")
    code2 = """
from app import app, db
from models import User

with app.app_context():
    user = User.query.filter_by(email="persistence_test@test.com").first()
    if user:
        print(f"Found user: {user.email}")
        print(f"User ID: {user.id}")
        print(f"Name: {user.first_name} {user.last_name}")
        print(f"Role: {user.role}")
    else:
        print("USER NOT FOUND - PERSISTENCE FAILED!")
        exit(1)
"""
    output2, code = run_in_separate_process(code2)
    print(output2.strip())
    if code != 0:
        print("\n   [FAILED] User not found in second process")
        return False

    time.sleep(1)

    # Step 3: Update the user in process #3
    print("\n3. Process #3: Updating user name...")
    code3 = """
from app import app, db
from models import User

with app.app_context():
    user = User.query.filter_by(email="persistence_test@test.com").first()
    user.first_name = "UpdatedName"
    db.session.commit()
    print(f"Updated name to: {user.first_name}")
"""
    output3, code = run_in_separate_process(code3)
    print(output3.strip())
    if code != 0:
        print("   [FAILED] Could not update user")
        result = subprocess.run(
            ["python", "-c", code3],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True
        )
        print("   Error output:", result.stderr)
        return False

    time.sleep(1)

    # Step 4: Verify name change persisted in process #4
    print("\n4. Process #4: Verifying name update...")
    code4 = """
from app import app, db
from models import User

with app.app_context():
    user = User.query.filter_by(email="persistence_test@test.com").first()
    # Check name
    if user.first_name == "UpdatedName":
        print(f"Name update verified: {user.first_name}")
    else:
        print(f"NAME UPDATE DID NOT PERSIST! Still: {user.first_name}")
        exit(1)
"""
    output4, code = run_in_separate_process(code4)
    print(output4.strip())
    if code != 0:
        print("   [FAILED] Password update did not persist")
        return False

    # Step 5: Clean up - delete test user in process #5
    print("\n5. Process #5: Cleaning up test user...")
    code5 = """
from app import app, db
from models import User

with app.app_context():
    user = User.query.filter_by(email="persistence_test@test.com").first()
    if user:
        db.session.delete(user)
        db.session.commit()
        print("Test user deleted")
"""
    output5, code = run_in_separate_process(code5)
    print(output5.strip())

    # Step 6: Verify deletion persisted in process #6
    print("\n6. Process #6: Verifying deletion...")
    code6 = """
from app import app, db
from models import User

with app.app_context():
    user = User.query.filter_by(email="persistence_test@test.com").first()
    if user:
        print("USER STILL EXISTS - DELETION DID NOT PERSIST!")
        exit(1)
    else:
        print("User successfully deleted (not found)")
"""
    output6, code = run_in_separate_process(code6)
    print(output6.strip())
    if code != 0:
        print("   [FAILED] Deletion did not persist")
        return False

    print("\n" + "="*60)
    print("[SUCCESS] All persistence tests passed!")
    print("="*60)
    print("\nDatabase is working correctly:")
    print("  - Data persists across separate Python processes")
    print("  - Create, Read, Update, Delete operations all work")
    print("  - No data loss between runs")
    print()

    return True

if __name__ == "__main__":
    success = test_persistence()
    sys.exit(0 if success else 1)

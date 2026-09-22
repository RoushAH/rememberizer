"""Service for bulk importing students from CSV files."""

import csv
import io
import re
from services.user_service import create_user
from services.group_service import add_student_to_group


def validate_email(email):
    """
    Validate email format.

    Args:
        email: Email string to validate

    Returns:
        bool: True if valid, False otherwise
    """
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def parse_csv_content(csv_content):
    """
    Parse CSV content and extract student data.

    Expected columns: first_name, last_name, email
    Column order doesn't matter as long as headers are present.

    Args:
        csv_content: String content of the CSV file

    Returns:
        tuple: (list of student dicts, list of validation errors)
    """
    students = []
    errors = []

    try:
        reader = csv.DictReader(io.StringIO(csv_content))

        # Validate headers
        if not reader.fieldnames:
            return [], ["CSV file is empty or has no headers"]

        # Normalize headers (lowercase, strip whitespace)
        headers = [h.lower().strip() for h in reader.fieldnames]

        required_headers = {"first_name", "last_name", "email"}
        missing = required_headers - set(headers)

        if missing:
            return [], [f"Missing required columns: {', '.join(missing)}"]

        # Create a mapping from normalized headers to original headers
        header_map = {}
        for orig, norm in zip(reader.fieldnames, headers):
            header_map[norm] = orig

        # Process each row
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
            first_name = row.get(header_map.get("first_name", "first_name"), "").strip()
            last_name = row.get(header_map.get("last_name", "last_name"), "").strip()
            email = row.get(header_map.get("email", "email"), "").strip().lower()

            row_errors = []

            if not first_name:
                row_errors.append("first_name is required")
            if not last_name:
                row_errors.append("last_name is required")
            if not email:
                row_errors.append("email is required")
            elif not validate_email(email):
                row_errors.append(f"invalid email format: {email}")

            if row_errors:
                errors.append(f"Row {row_num}: {'; '.join(row_errors)}")
            else:
                students.append(
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                    }
                )

    except csv.Error as e:
        return [], [f"CSV parsing error: {str(e)}"]

    return students, errors


def bulk_import_students(csv_content, organization_id, created_by_id, group_id=None):
    """
    Import students from CSV content.

    Args:
        csv_content: String content of the CSV file
        organization_id: ID of the organization for new students
        created_by_id: ID of the teacher importing
        group_id: Optional group ID to add students to

    Returns:
        dict: Summary with created, errors, and skipped counts
    """
    students, parse_errors = parse_csv_content(csv_content)

    if parse_errors and not students:
        # All rows had errors
        return {
            "created": 0,
            "skipped": 0,
            "errors": parse_errors,
            "created_students": [],
        }

    created_count = 0
    skipped_count = 0
    import_errors = list(parse_errors)  # Include parse errors
    created_students = []

    for student_data in students:
        try:
            student = create_user(
                email=student_data["email"],
                password=None,  # Token-based setup
                role="student",
                first_name=student_data["first_name"],
                last_name=student_data["last_name"],
                organization_id=organization_id,
                created_by_id=created_by_id,
            )

            created_count += 1
            created_students.append(student)

            # Add to group if specified
            if group_id:
                try:
                    add_student_to_group(group_id, student.id)
                except ValueError:
                    # Already in group somehow, ignore
                    pass

        except ValueError as e:
            error_msg = str(e)
            if "Email already exists" in error_msg:
                skipped_count += 1
                import_errors.append(
                    f"{student_data['email']}: skipped (email already exists)"
                )
            else:
                import_errors.append(f"{student_data['email']}: {error_msg}")

    return {
        "created": created_count,
        "skipped": skipped_count,
        "errors": import_errors,
        "created_students": created_students,
    }


def generate_sample_csv():
    """
    Generate sample CSV content for download.

    Returns:
        str: Sample CSV content
    """
    return """first_name,last_name,email
John,Smith,john.smith@example.com
Jane,Doe,jane.doe@example.com
Alex,Johnson,alex.johnson@example.com"""

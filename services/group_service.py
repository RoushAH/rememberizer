"""Service for managing student groups and bulk operations."""

from models import (
    db,
    User,
    StudentGroup,
    StudentGroupMembership,
    UserDomainAssignment,
)


def create_group(name, organization_id, created_by_id):
    """
    Create a new student group.

    Args:
        name: Name of the group (e.g., "Period 1")
        organization_id: ID of the organization
        created_by_id: ID of the teacher creating the group

    Returns:
        StudentGroup: The created group

    Raises:
        ValueError: If name is empty or group already exists
    """
    if not name or not name.strip():
        raise ValueError("Group name is required")

    name = name.strip()

    # Check for duplicate name in organization
    existing = StudentGroup.query.filter_by(
        name=name, organization_id=organization_id, is_active=True
    ).first()
    if existing:
        raise ValueError(f"A group named '{name}' already exists")

    group = StudentGroup(
        name=name,
        organization_id=organization_id,
        created_by=created_by_id,
    )
    db.session.add(group)
    db.session.commit()

    return group


def get_groups_by_organization(organization_id):
    """
    Get all active groups in an organization.

    Args:
        organization_id: ID of the organization

    Returns:
        list: List of StudentGroup objects
    """
    return (
        StudentGroup.query.filter_by(organization_id=organization_id, is_active=True)
        .order_by(StudentGroup.name)
        .all()
    )


def get_group_by_id(group_id):
    """
    Get a group by ID.

    Args:
        group_id: ID of the group

    Returns:
        StudentGroup or None
    """
    return StudentGroup.query.get(group_id)


def add_student_to_group(group_id, student_id):
    """
    Add a student to a group.

    Args:
        group_id: ID of the group
        student_id: ID of the student

    Returns:
        StudentGroupMembership: The created membership

    Raises:
        ValueError: If student is already in the group or student/group doesn't exist
    """
    group = StudentGroup.query.get(group_id)
    if not group:
        raise ValueError("Group not found")

    student = User.query.get(student_id)
    if not student or student.role != "student":
        raise ValueError("Student not found")

    # Check if already a member
    existing = StudentGroupMembership.query.filter_by(
        group_id=group_id, student_id=student_id
    ).first()
    if existing:
        raise ValueError("Student is already in this group")

    membership = StudentGroupMembership(
        group_id=group_id,
        student_id=student_id,
    )
    db.session.add(membership)
    db.session.commit()

    return membership


def remove_student_from_group(group_id, student_id):
    """
    Remove a student from a group.

    Args:
        group_id: ID of the group
        student_id: ID of the student

    Raises:
        ValueError: If membership doesn't exist
    """
    membership = StudentGroupMembership.query.filter_by(
        group_id=group_id, student_id=student_id
    ).first()

    if not membership:
        raise ValueError("Student is not in this group")

    db.session.delete(membership)
    db.session.commit()


def get_students_in_group(group_id):
    """
    Get all students in a group.

    Args:
        group_id: ID of the group

    Returns:
        list: List of User objects (students)
    """
    memberships = StudentGroupMembership.query.filter_by(group_id=group_id).all()
    return [m.student for m in memberships if m.student.is_active]


def get_groups_for_student(student_id):
    """
    Get all groups a student belongs to.

    Args:
        student_id: ID of the student

    Returns:
        list: List of StudentGroup objects
    """
    memberships = StudentGroupMembership.query.filter_by(student_id=student_id).all()
    return [m.group for m in memberships if m.group.is_active]


def bulk_assign_domain_to_group(group_id, domain_id, assigned_by_id):
    """
    Assign a domain to all students in a group.

    Args:
        group_id: ID of the group
        domain_id: ID of the domain to assign
        assigned_by_id: ID of the teacher assigning

    Returns:
        dict: Summary with counts of assigned, skipped (already had)
    """
    students = get_students_in_group(group_id)

    assigned_count = 0
    skipped_count = 0

    for student in students:
        # Check if already assigned
        existing = UserDomainAssignment.query.filter_by(
            user_id=student.id, domain_id=domain_id
        ).first()

        if existing:
            skipped_count += 1
        else:
            assignment = UserDomainAssignment(
                user_id=student.id,
                domain_id=domain_id,
                assigned_by=assigned_by_id,
            )
            db.session.add(assignment)
            assigned_count += 1

    db.session.commit()

    return {
        "assigned": assigned_count,
        "skipped": skipped_count,
        "total": len(students),
    }


def bulk_unassign_domain_from_group(group_id, domain_id):
    """
    Unassign a domain from all students in a group.

    Args:
        group_id: ID of the group
        domain_id: ID of the domain to unassign

    Returns:
        dict: Summary with count of removed assignments
    """
    students = get_students_in_group(group_id)
    removed_count = 0

    for student in students:
        assignment = UserDomainAssignment.query.filter_by(
            user_id=student.id, domain_id=domain_id
        ).first()

        if assignment:
            db.session.delete(assignment)
            removed_count += 1

    db.session.commit()

    return {
        "removed": removed_count,
        "total": len(students),
    }


def deactivate_group(group_id):
    """
    Deactivate (soft delete) a group.

    Args:
        group_id: ID of the group

    Raises:
        ValueError: If group doesn't exist
    """
    group = StudentGroup.query.get(group_id)
    if not group:
        raise ValueError("Group not found")

    group.is_active = False
    db.session.commit()


def get_group_progress_summary(group_id):
    """
    Get progress summary for all students in a group.

    Args:
        group_id: ID of the group

    Returns:
        list: List of dicts with student progress info
    """
    from services.domain_service import get_user_domains
    from services.progress_service import (
        get_progress_string,
        get_questions_answered_today,
        is_domain_complete,
    )
    from models import Attempt

    students = get_students_in_group(group_id)
    progress_data = []

    for student in students:
        assigned_domains = get_user_domains(student.id)
        questions_today = get_questions_answered_today(student.id)
        total_questions = Attempt.query.filter_by(user_id=student.id).count()

        # Get domain progress
        domain_progress = []
        for domain in assigned_domains:
            progress_str = get_progress_string(domain.id, student.id)
            is_complete = is_domain_complete(student.id, domain.id)
            domain_progress.append(
                {
                    "domain": domain,
                    "progress": progress_str,
                    "is_complete": is_complete,
                }
            )

        progress_data.append(
            {
                "student": student,
                "domain_progress": domain_progress,
                "questions_today": questions_today,
                "total_questions": total_questions,
            }
        )

    return progress_data

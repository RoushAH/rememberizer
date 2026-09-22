"""Service for managing assignment templates."""

import json
from models import db, Domain, AssignmentTemplate
from services.group_service import bulk_assign_domain_to_group


def create_template(name, domain_ids, organization_id, created_by_id):
    """
    Create a new assignment template.

    Args:
        name: Name of the template
        domain_ids: List of domain IDs to include
        organization_id: ID of the organization
        created_by_id: ID of the teacher creating the template

    Returns:
        AssignmentTemplate: The created template

    Raises:
        ValueError: If name is empty or no domains selected
    """
    if not name or not name.strip():
        raise ValueError("Template name is required")

    if not domain_ids or len(domain_ids) == 0:
        raise ValueError("At least one domain must be selected")

    name = name.strip()

    # Check for duplicate name in organization
    existing = AssignmentTemplate.query.filter_by(
        name=name, organization_id=organization_id
    ).first()
    if existing:
        raise ValueError(f"A template named '{name}' already exists")

    # Validate domain IDs exist
    for domain_id in domain_ids:
        domain = Domain.query.get(domain_id)
        if not domain:
            raise ValueError(f"Domain {domain_id} not found")

    template = AssignmentTemplate(
        name=name,
        domain_ids=json.dumps(domain_ids),
        organization_id=organization_id,
        created_by=created_by_id,
    )
    db.session.add(template)
    db.session.commit()

    return template


def get_templates_by_organization(organization_id):
    """
    Get all templates in an organization.

    Args:
        organization_id: ID of the organization

    Returns:
        list: List of AssignmentTemplate objects
    """
    return (
        AssignmentTemplate.query.filter_by(organization_id=organization_id)
        .order_by(AssignmentTemplate.name)
        .all()
    )


def get_template_by_id(template_id):
    """
    Get a template by ID.

    Args:
        template_id: ID of the template

    Returns:
        AssignmentTemplate or None
    """
    return AssignmentTemplate.query.get(template_id)


def get_template_domains(template_id):
    """
    Get domains included in a template.

    Args:
        template_id: ID of the template

    Returns:
        list: List of Domain objects
    """
    template = AssignmentTemplate.query.get(template_id)
    if not template:
        return []

    domain_ids = template.get_domain_ids()
    domains = []
    for domain_id in domain_ids:
        domain = Domain.query.get(domain_id)
        if domain:
            domains.append(domain)

    return domains


def apply_template_to_group(template_id, group_id, assigned_by_id):
    """
    Apply a template to a group (assign all template domains to all students).

    Args:
        template_id: ID of the template
        group_id: ID of the group
        assigned_by_id: ID of the teacher assigning

    Returns:
        dict: Summary with assignment counts per domain

    Raises:
        ValueError: If template or group not found
    """
    template = AssignmentTemplate.query.get(template_id)
    if not template:
        raise ValueError("Template not found")

    domain_ids = template.get_domain_ids()

    results = {
        "template_name": template.name,
        "domains": [],
        "total_assigned": 0,
        "total_skipped": 0,
    }

    for domain_id in domain_ids:
        domain = Domain.query.get(domain_id)
        if not domain:
            continue

        result = bulk_assign_domain_to_group(group_id, domain_id, assigned_by_id)

        results["domains"].append(
            {
                "domain_name": domain.name,
                "assigned": result["assigned"],
                "skipped": result["skipped"],
            }
        )
        results["total_assigned"] += result["assigned"]
        results["total_skipped"] += result["skipped"]

    return results


def apply_template_to_student(template_id, student_id, assigned_by_id):
    """
    Apply a template to a single student.

    Args:
        template_id: ID of the template
        student_id: ID of the student
        assigned_by_id: ID of the teacher assigning

    Returns:
        dict: Summary with assignment counts

    Raises:
        ValueError: If template not found
    """
    from services.domain_service import assign_domain_to_user

    template = AssignmentTemplate.query.get(template_id)
    if not template:
        raise ValueError("Template not found")

    domain_ids = template.get_domain_ids()

    results = {
        "template_name": template.name,
        "assigned": 0,
        "skipped": 0,
        "domains": [],
    }

    for domain_id in domain_ids:
        domain = Domain.query.get(domain_id)
        if not domain:
            continue

        try:
            assign_domain_to_user(student_id, domain_id, assigned_by_id)
            results["assigned"] += 1
            results["domains"].append(
                {
                    "domain_name": domain.name,
                    "status": "assigned",
                }
            )
        except ValueError:
            results["skipped"] += 1
            results["domains"].append(
                {
                    "domain_name": domain.name,
                    "status": "already assigned",
                }
            )

    return results


def delete_template(template_id):
    """
    Delete a template.

    Args:
        template_id: ID of the template

    Raises:
        ValueError: If template not found
    """
    template = AssignmentTemplate.query.get(template_id)
    if not template:
        raise ValueError("Template not found")

    db.session.delete(template)
    db.session.commit()


def update_template(template_id, name=None, domain_ids=None):
    """
    Update a template.

    Args:
        template_id: ID of the template
        name: New name (optional)
        domain_ids: New list of domain IDs (optional)

    Returns:
        AssignmentTemplate: The updated template

    Raises:
        ValueError: If template not found or validation fails
    """
    template = AssignmentTemplate.query.get(template_id)
    if not template:
        raise ValueError("Template not found")

    if name is not None:
        if not name.strip():
            raise ValueError("Template name cannot be empty")
        template.name = name.strip()

    if domain_ids is not None:
        if len(domain_ids) == 0:
            raise ValueError("At least one domain must be selected")
        # Validate domain IDs exist
        for domain_id in domain_ids:
            domain = Domain.query.get(domain_id)
            if not domain:
                raise ValueError(f"Domain {domain_id} not found")
        template.domain_ids = json.dumps(domain_ids)

    db.session.commit()
    return template

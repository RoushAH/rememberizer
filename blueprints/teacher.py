"""Teacher blueprint for managing students and domains."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user, login_required
from models import db, User, Domain
from services.user_service import create_user
from services.image_service import (
    discard_uploaded_images,
    resolve_image_references,
    save_uploaded_images,
)
import json
import csv
import io

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")


def require_teacher_or_admin():
    """Check if current user is teacher or admin, abort if not."""
    if not current_user.is_authenticated or current_user.role not in [
        "teacher",
        "admin",
    ]:
        abort(403)


# ============================================================================
# TEACHER DASHBOARD
# ============================================================================


@teacher_bp.route("/dashboard")
@login_required
def dashboard():
    """Teacher dashboard showing all students and their progress."""
    from services.user_service import get_students_by_teacher
    from services.domain_service import get_user_domains
    from services.progress_service import (
        get_progress_string,
        get_questions_answered_today,
        is_domain_complete,
    )
    from models import Domain, Attempt

    require_teacher_or_admin()

    # Get all students in teacher's organization
    students = get_students_by_teacher(current_user.id)

    # Get available domains for display
    domains = Domain.query.all()

    # Prepare student data with progress info
    student_data = []
    for student in students:
        # Get assigned domains
        assigned_domains = get_user_domains(student.id)

        # Get progress strings for each assigned domain
        domain_progress = []
        for domain in assigned_domains:
            progress_str = get_progress_string(domain.id, student.id)
            is_complete = is_domain_complete(student.id, domain.id)
            domain_progress.append(
                {"domain": domain, "progress": progress_str, "is_complete": is_complete}
            )

        # Get engagement metrics
        questions_today = get_questions_answered_today(student.id)
        total_questions = Attempt.query.filter_by(user_id=student.id).count()

        student_data.append(
            {
                "student": student,
                "assigned_domains": assigned_domains,
                "domain_progress": domain_progress,
                "total_domains": len(assigned_domains),
                "questions_today": questions_today,
                "total_questions": total_questions,
            }
        )

    return render_template(
        "teacher/dashboard.html", student_data=student_data, available_domains=domains
    )


# ============================================================================
# TEACHER DOMAIN MANAGEMENT ROUTES
# ============================================================================


@teacher_bp.route("/domains")
@login_required
def domains():
    """List all available domains with testing option."""
    from services.domain_service import get_visible_domains
    from services.progress_service import (
        get_student_domain_progress,
        is_domain_complete,
    )

    require_teacher_or_admin()

    # Get domains visible to this teacher
    visible_domains = get_visible_domains(current_user.id, current_user.organization_id)

    # For each domain, get teacher's progress
    domain_data = []
    for domain in visible_domains:
        progress = get_student_domain_progress(current_user.id, domain.id)
        if progress:
            progress["is_complete"] = is_domain_complete(current_user.id, domain.id)
        domain_data.append(
            {
                "domain": domain,
                "progress": progress,
                "created_by_me": domain.created_by == current_user.id,
            }
        )

    return render_template("teacher/domains.html", domain_data=domain_data)


@teacher_bp.route("/domains/create", methods=["GET"])
@login_required
def create_domain_form():
    """Display domain creation form."""
    require_teacher_or_admin()

    # ?tab= reopens the tab a failed submission came from
    return render_template(
        "teacher/create_domain.html", active_tab=request.args.get("tab", "form")
    )


@teacher_bp.route("/domains/create", methods=["POST"])
@login_required
def create_domain():
    """Process domain creation (form or CSV)."""
    require_teacher_or_admin()

    upload_method = request.form.get("upload_method")  # "form" or "csv"

    if upload_method == "csv":
        # Handle CSV upload
        if "csv_file" not in request.files:
            flash("No file uploaded", "error")
            return redirect(url_for("teacher.create_domain_form"))

        file = request.files["csv_file"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(url_for("teacher.create_domain_form"))

        if not file.filename.endswith(".csv"):
            flash("File must be a CSV", "error")
            return redirect(url_for("teacher.create_domain_form"))

        domain_name = request.form.get("domain_name", "").strip()
        if not domain_name:
            flash("Domain name is required", "error")
            return redirect(url_for("teacher.create_domain_form"))

        # Parse CSV
        uploaded_images = {}
        try:
            csv_content = file.read().decode("utf-8")
            csv_reader = csv.DictReader(io.StringIO(csv_content))

            # First row is header (field names)
            field_names = list(csv_reader.fieldnames)

            # Read all facts
            facts_data = [row for row in csv_reader]

            # Swap "img:erato.png" cells for the stored upload path
            uploaded_images = save_uploaded_images(request.files.getlist("image_files"))
            facts_data = resolve_image_references(facts_data, uploaded_images)

            # Create domain
            from services.domain_service import create_custom_domain

            domain = create_custom_domain(
                name=domain_name,
                field_names=field_names,
                facts_data=facts_data,
                created_by=current_user.id,
                organization_id=current_user.organization_id,
            )

            flash(
                f"Domain '{domain.name}' created from CSV with "
                f"{len(facts_data)} facts!",
                "success",
            )
            return redirect(url_for("teacher.domains"))

        except ValueError as e:
            discard_uploaded_images(uploaded_images.values())
            flash(f"Validation error: {str(e)}", "error")
            return redirect(url_for("teacher.create_domain_form"))
        except Exception as e:
            discard_uploaded_images(uploaded_images.values())
            flash(f"Error processing CSV: {str(e)}", "error")
            return redirect(url_for("teacher.create_domain_form"))

    else:
        # Handle form creation
        domain_name = request.form.get("domain_name", "").strip()
        field_names_raw = request.form.get("field_names", "").strip()
        facts_json = request.form.get("facts_json", "").strip()

        # Validate inputs
        if not domain_name or not field_names_raw or not facts_json:
            flash("All fields are required", "error")
            return redirect(url_for("teacher.create_domain_form"))

        # Parse field names (comma-separated)
        field_names = [f.strip() for f in field_names_raw.split(",")]

        # Parse facts (JSON array)
        try:
            facts_data = json.loads(facts_json)
        except json.JSONDecodeError:
            flash("Invalid JSON format for facts", "error")
            return redirect(url_for("teacher.create_domain_form"))

        # Validate facts structure
        for fact in facts_data:
            if not all(field in fact for field in field_names):
                flash(
                    f"Each fact must have all fields: {', '.join(field_names)}", "error"
                )
                return redirect(url_for("teacher.create_domain_form"))

        # Create domain and facts
        uploaded_images = {}
        try:
            from services.domain_service import create_custom_domain

            # Swap "img:erato.png" values for the stored upload path
            uploaded_images = save_uploaded_images(request.files.getlist("image_files"))
            facts_data = resolve_image_references(facts_data, uploaded_images)

            domain = create_custom_domain(
                name=domain_name,
                field_names=field_names,
                facts_data=facts_data,
                created_by=current_user.id,
                organization_id=current_user.organization_id,
            )

            flash(f"Domain '{domain.name}' created successfully!", "success")
            return redirect(url_for("teacher.domains"))

        except ValueError as e:
            discard_uploaded_images(uploaded_images.values())
            flash(f"Validation error: {str(e)}", "error")
            return redirect(url_for("teacher.create_domain_form"))


@teacher_bp.route("/domains/import-photos", methods=["POST"])
@login_required
def import_photo_roster():
    """
    Create a domain from a roster CSV plus a folder or zip of photos.

    The CSV's first column names the photo file (without its extension); every
    other column becomes a field to quiz. See services/photo_roster_service.py.
    """
    from services.domain_service import create_custom_domain
    from services.photo_roster_service import (
        build_photo_facts,
        collect_photo_files,
        collect_zip_photos,
        decode_csv,
        format_import_report,
    )

    require_teacher_or_admin()

    back = redirect(url_for("teacher.create_domain_form", tab="photos"))

    domain_name = request.form.get("domain_name", "").strip()
    if not domain_name:
        flash("Domain name is required", "error")
        return back

    csv_file = request.files.get("csv_file")
    if not csv_file or not csv_file.filename:
        flash("No CSV file selected", "error")
        return back
    if not csv_file.filename.lower().endswith(".csv"):
        flash("File must be a CSV", "error")
        return back

    zip_file = request.files.get("photo_zip")

    # Blank means "quiz every column", so an untouched box must not look chosen
    include_columns = [
        column
        for column in request.form.get("include_columns", "").split(",")
        if column.strip()
    ]

    result = None
    try:
        # A zip and a folder are alternatives; the zip wins if both are given.
        if zip_file and zip_file.filename:
            photos = collect_zip_photos(zip_file)
        else:
            photos = collect_photo_files(request.files.getlist("photo_files"))

        if not photos:
            raise ValueError(
                "No photos found - choose the folder or zip that holds them "
                "(PNG, JPG, GIF or WebP)"
            )

        result = build_photo_facts(
            decode_csv(csv_file.read()),
            photos,
            photo_field=request.form.get("photo_field", "").strip(),
            include_columns=include_columns,
        )

        domain = create_custom_domain(
            name=domain_name,
            field_names=result["field_names"],
            facts_data=result["facts_data"],
            created_by=current_user.id,
            organization_id=current_user.organization_id,
        )

    except ValueError as e:
        if result:
            discard_uploaded_images(result["image_values"])
        flash(f"Import failed: {str(e)}", "error")
        return back
    except Exception as e:
        if result:
            discard_uploaded_images(result["image_values"])
        flash(f"Error processing the roster: {str(e)}", "error")
        return back

    report = format_import_report(result)
    flash(
        f"Domain '{domain.name}' created with {len(result['facts_data'])} "
        f"photo facts. {report}".strip(),
        "success",
    )
    return redirect(url_for("teacher.domains"))


@teacher_bp.route("/domains/<int:domain_id>/publish", methods=["POST"])
@login_required
def toggle_publish_domain(domain_id):
    """Publish or unpublish a domain (creator only)."""
    from services.domain_service import update_domain_published_status

    require_teacher_or_admin()

    domain = Domain.query.get_or_404(domain_id)

    # Verify creator (or admin)
    if domain.created_by != current_user.id and current_user.role != "admin":
        abort(403)

    # Toggle published status
    action = request.form.get("action")  # "publish" or "unpublish"
    is_published = action == "publish"

    update_domain_published_status(domain_id, is_published)

    status = "published" if is_published else "unpublished"
    flash(f"Domain '{domain.name}' {status} successfully!", "success")
    return redirect(url_for("teacher.domains"))


# ============================================================================
# END TEACHER DOMAIN MANAGEMENT ROUTES
# ============================================================================


# ============================================================================
# TEACHER STUDENT MANAGEMENT ROUTES
# ============================================================================


@teacher_bp.route("/students/create", methods=["GET", "POST"])
@login_required
def create_student():
    """Create a new student."""
    require_teacher_or_admin()

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")

        try:
            # Import here to avoid circular import
            from app import send_user_setup_notification

            # Create student WITHOUT password (they'll set it via token)
            student = create_user(
                email=email,
                password=None,  # No password - use token-based setup
                role="student",
                first_name=first_name,
                last_name=last_name,
                organization_id=current_user.organization_id,
                created_by_id=current_user.id,
            )

            # Send setup notification (email or display link)
            send_user_setup_notification(student, "Student")

            return redirect(url_for("teacher.dashboard"))

        except ValueError as e:
            flash(str(e), "error")
            return render_template("teacher/create_student.html")

    return render_template("teacher/create_student.html")


@teacher_bp.route("/students/<int:student_id>")
@login_required
def student_detail(student_id):
    """View detailed student progress."""
    from services.domain_service import get_user_domains
    from services.progress_service import (
        get_student_domain_progress,
        get_questions_answered_today,
        get_total_time_spent,
        get_unique_session_count,
        format_time_spent,
        is_domain_complete,
    )
    from services.streak_service import get_streak_info
    from models import User, Domain, Attempt

    require_teacher_or_admin()

    student = User.query.get(student_id)

    if not student or student.role != "student":
        flash("Student not found", "error")
        return redirect(url_for("teacher.dashboard"))

    # Check student is in same org
    if student.organization_id != current_user.organization_id:
        abort(403)

    # Get assigned domains with detailed progress
    assigned_domains = get_user_domains(student.id)
    all_domains = Domain.query.all()

    domain_details = []
    for domain in all_domains:
        is_assigned = any(d.id == domain.id for d in assigned_domains)

        if is_assigned:
            progress_data = get_student_domain_progress(student.id, domain.id)
            if progress_data:
                progress_data["is_complete"] = is_domain_complete(student.id, domain.id)
            domain_details.append(
                {"domain": domain, "is_assigned": True, "progress": progress_data}
            )
        else:
            domain_details.append(
                {"domain": domain, "is_assigned": False, "progress": None}
            )

    # Get engagement metrics
    questions_today = get_questions_answered_today(student.id)
    total_time_minutes = get_total_time_spent(student.id)
    session_count = get_unique_session_count(student.id)
    formatted_time = format_time_spent(total_time_minutes)
    total_questions = Attempt.query.filter_by(user_id=student.id).count()

    # Get streak info for this student
    streak_info = get_streak_info(student.id)

    return render_template(
        "teacher/student_detail.html",
        student=student,
        domain_details=domain_details,
        questions_today=questions_today,
        formatted_time=formatted_time,
        session_count=session_count,
        total_questions=total_questions,
        streak_info=streak_info,
    )


@teacher_bp.route("/students/<int:student_id>/assign", methods=["POST"])
@login_required
def assign_domain_to_student(student_id):
    """Assign a domain to a student."""
    from services.domain_service import assign_domain_to_user
    from models import User

    require_teacher_or_admin()

    student = User.query.get(student_id)
    if not student or student.role != "student":
        flash("Student not found", "error")
        return redirect(url_for("teacher.dashboard"))

    # Check student is in same org
    if student.organization_id != current_user.organization_id:
        abort(403)

    domain_id = request.form.get("domain_id", type=int)
    if not domain_id:
        flash("No domain selected", "error")
        return redirect(url_for("teacher.student_detail", student_id=student_id))

    try:
        assign_domain_to_user(student.id, domain_id, current_user.id)
        from models import Domain

        domain = Domain.query.get(domain_id)
        flash(f"Assigned {domain.name} to {student.get_full_name()}", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("teacher.student_detail", student_id=student_id))


@teacher_bp.route("/students/<int:student_id>/unassign", methods=["POST"])
@login_required
def unassign_domain_from_student(student_id):
    """Unassign a domain from a student."""
    from services.domain_service import unassign_domain_from_user
    from models import User

    require_teacher_or_admin()

    student = User.query.get(student_id)
    if not student or student.role != "student":
        flash("Student not found", "error")
        return redirect(url_for("teacher.dashboard"))

    # Check student is in same org
    if student.organization_id != current_user.organization_id:
        abort(403)

    domain_id = request.form.get("domain_id", type=int)
    if not domain_id:
        flash("No domain selected", "error")
        return redirect(url_for("teacher.student_detail", student_id=student_id))

    try:
        unassign_domain_from_user(student.id, domain_id)
        from models import Domain

        domain = Domain.query.get(domain_id)
        flash(f"Unassigned {domain.name} from {student.get_full_name()}", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("teacher.student_detail", student_id=student_id))


@teacher_bp.route(
    "/students/<int:student_id>/reset-domain/<int:domain_id>", methods=["POST"]
)
@login_required
def reset_student_domain_progress(student_id, domain_id):
    """Reset a student's progress for a specific domain."""
    from services.fact_service import reset_domain_progress
    from models import User, Domain

    require_teacher_or_admin()

    student = User.query.get(student_id)
    if not student or student.role != "student":
        flash("Student not found", "error")
        return redirect(url_for("teacher.dashboard"))

    # Check student is in same org
    if student.organization_id != current_user.organization_id:
        abort(403)

    domain = Domain.query.get(domain_id)
    if not domain:
        flash("Domain not found", "error")
        return redirect(url_for("teacher.student_detail", student_id=student_id))

    # Reset progress for this student only
    reset_domain_progress(domain_id, student.id)
    flash(f"Reset {student.get_full_name()}'s progress for {domain.name}", "success")

    return redirect(url_for("teacher.student_detail", student_id=student_id))


@teacher_bp.route("/students/<int:student_id>/deactivate", methods=["POST"])
@login_required
def deactivate_student(student_id):
    """Deactivate a student."""
    require_teacher_or_admin()

    student = User.query.get(student_id)
    if not student or student.role != "student":
        flash("Student not found", "error")
        return redirect(url_for("teacher.dashboard"))

    # Check student is in same org
    if student.organization_id != current_user.organization_id:
        abort(403)

    student.is_active = False
    db.session.commit()

    flash(f"Student {student.get_full_name()} deactivated", "success")
    return redirect(url_for("teacher.dashboard"))


# ============================================================================
# END TEACHER STUDENT MANAGEMENT ROUTES
# ============================================================================


# ============================================================================
# GROUP MANAGEMENT ROUTES
# ============================================================================


@teacher_bp.route("/groups")
@login_required
def groups():
    """List all groups."""
    from services.group_service import (
        get_groups_by_organization,
        get_students_in_group,
    )

    require_teacher_or_admin()

    all_groups = get_groups_by_organization(current_user.organization_id)

    # Add student count to each group
    group_data = []
    for group in all_groups:
        students = get_students_in_group(group.id)
        group_data.append(
            {
                "group": group,
                "student_count": len(students),
            }
        )

    return render_template("teacher/groups.html", group_data=group_data)


@teacher_bp.route("/groups/create", methods=["GET", "POST"])
@login_required
def create_group():
    """Create a new group."""
    from services.group_service import create_group as create_group_service

    require_teacher_or_admin()

    if request.method == "POST":
        name = request.form.get("name", "").strip()

        try:
            group = create_group_service(
                name=name,
                organization_id=current_user.organization_id,
                created_by_id=current_user.id,
            )
            flash(f"Group '{group.name}' created successfully!", "success")
            return redirect(url_for("teacher.group_detail", group_id=group.id))
        except ValueError as e:
            flash(str(e), "error")

    return render_template("teacher/create_group.html")


@teacher_bp.route("/groups/<int:group_id>")
@login_required
def group_detail(group_id):
    """View group details and manage members."""
    from services.group_service import (
        get_group_by_id,
        get_students_in_group,
        get_group_progress_summary,
    )
    from services.user_service import get_students_by_teacher
    from services.template_service import get_templates_by_organization

    require_teacher_or_admin()

    group = get_group_by_id(group_id)
    if not group or group.organization_id != current_user.organization_id:
        flash("Group not found", "error")
        return redirect(url_for("teacher.groups"))

    # Get students in group
    group_students = get_students_in_group(group_id)
    group_student_ids = [s.id for s in group_students]

    # Get progress summary
    progress_data = get_group_progress_summary(group_id)

    # Get all students for adding to group
    all_students = get_students_by_teacher(current_user.id)
    available_students = [s for s in all_students if s.id not in group_student_ids]

    # Get available domains
    all_domains = Domain.query.all()

    # Get templates
    templates = get_templates_by_organization(current_user.organization_id)

    return render_template(
        "teacher/group_detail.html",
        group=group,
        progress_data=progress_data,
        available_students=available_students,
        available_domains=all_domains,
        templates=templates,
    )


@teacher_bp.route("/groups/<int:group_id>/add-student", methods=["POST"])
@login_required
def add_student_to_group(group_id):
    """Add a student to a group."""
    from services.group_service import (
        get_group_by_id,
        add_student_to_group as add_student_service,
    )

    require_teacher_or_admin()

    group = get_group_by_id(group_id)
    if not group or group.organization_id != current_user.organization_id:
        flash("Group not found", "error")
        return redirect(url_for("teacher.groups"))

    student_id = request.form.get("student_id", type=int)
    if not student_id:
        flash("No student selected", "error")
        return redirect(url_for("teacher.group_detail", group_id=group_id))

    try:
        add_student_service(group_id, student_id)
        student = User.query.get(student_id)
        flash(f"Added {student.get_full_name()} to {group.name}", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("teacher.group_detail", group_id=group_id))


@teacher_bp.route("/groups/<int:group_id>/remove-student", methods=["POST"])
@login_required
def remove_student_from_group(group_id):
    """Remove a student from a group."""
    from services.group_service import (
        get_group_by_id,
        remove_student_from_group as remove_student_service,
    )

    require_teacher_or_admin()

    group = get_group_by_id(group_id)
    if not group or group.organization_id != current_user.organization_id:
        flash("Group not found", "error")
        return redirect(url_for("teacher.groups"))

    student_id = request.form.get("student_id", type=int)
    if not student_id:
        flash("No student selected", "error")
        return redirect(url_for("teacher.group_detail", group_id=group_id))

    try:
        remove_student_service(group_id, student_id)
        student = User.query.get(student_id)
        flash(f"Removed {student.get_full_name()} from {group.name}", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("teacher.group_detail", group_id=group_id))


@teacher_bp.route("/groups/<int:group_id>/assign-domain", methods=["POST"])
@login_required
def bulk_assign_domain(group_id):
    """Assign a domain to all students in a group."""
    from services.group_service import get_group_by_id, bulk_assign_domain_to_group

    require_teacher_or_admin()

    group = get_group_by_id(group_id)
    if not group or group.organization_id != current_user.organization_id:
        flash("Group not found", "error")
        return redirect(url_for("teacher.groups"))

    domain_id = request.form.get("domain_id", type=int)
    if not domain_id:
        flash("No domain selected", "error")
        return redirect(url_for("teacher.group_detail", group_id=group_id))

    result = bulk_assign_domain_to_group(group_id, domain_id, current_user.id)

    domain = Domain.query.get(domain_id)
    flash(
        f"Assigned {domain.name}: {result['assigned']} added, "
        f"{result['skipped']} already had it",
        "success",
    )

    return redirect(url_for("teacher.group_detail", group_id=group_id))


@teacher_bp.route("/groups/<int:group_id>/apply-template", methods=["POST"])
@login_required
def apply_template_to_group(group_id):
    """Apply an assignment template to a group."""
    from services.group_service import get_group_by_id
    from services.template_service import (
        apply_template_to_group as apply_template_service,
    )

    require_teacher_or_admin()

    group = get_group_by_id(group_id)
    if not group or group.organization_id != current_user.organization_id:
        flash("Group not found", "error")
        return redirect(url_for("teacher.groups"))

    template_id = request.form.get("template_id", type=int)
    if not template_id:
        flash("No template selected", "error")
        return redirect(url_for("teacher.group_detail", group_id=group_id))

    try:
        result = apply_template_service(template_id, group_id, current_user.id)
        flash(
            f"Applied '{result['template_name']}': {result['total_assigned']} "
            f"assignments added, {result['total_skipped']} skipped",
            "success",
        )
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("teacher.group_detail", group_id=group_id))


@teacher_bp.route("/groups/<int:group_id>/deactivate", methods=["POST"])
@login_required
def deactivate_group(group_id):
    """Deactivate a group."""
    from services.group_service import get_group_by_id, deactivate_group as deactivate

    require_teacher_or_admin()

    group = get_group_by_id(group_id)
    if not group or group.organization_id != current_user.organization_id:
        flash("Group not found", "error")
        return redirect(url_for("teacher.groups"))

    try:
        deactivate(group_id)
        flash(f"Group '{group.name}' deactivated", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("teacher.groups"))


# ============================================================================
# END GROUP MANAGEMENT ROUTES
# ============================================================================


# ============================================================================
# BULK IMPORT ROUTES
# ============================================================================


@teacher_bp.route("/students/bulk-import", methods=["GET", "POST"])
@login_required
def bulk_import():
    """Bulk import students from CSV."""
    from services.bulk_import_service import bulk_import_students, generate_sample_csv
    from services.group_service import get_groups_by_organization

    require_teacher_or_admin()

    groups = get_groups_by_organization(current_user.organization_id)

    if request.method == "POST":
        if "csv_file" not in request.files:
            flash("No file uploaded", "error")
            return redirect(url_for("teacher.bulk_import"))

        file = request.files["csv_file"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(url_for("teacher.bulk_import"))

        if not file.filename.endswith(".csv"):
            flash("File must be a CSV", "error")
            return redirect(url_for("teacher.bulk_import"))

        group_id = request.form.get("group_id", type=int)

        try:
            csv_content = file.read().decode("utf-8")
            result = bulk_import_students(
                csv_content=csv_content,
                organization_id=current_user.organization_id,
                created_by_id=current_user.id,
                group_id=group_id if group_id else None,
            )

            return render_template(
                "teacher/import_results.html",
                result=result,
                group_id=group_id,
            )

        except Exception as e:
            flash(f"Error processing CSV: {str(e)}", "error")
            return redirect(url_for("teacher.bulk_import"))

    sample_csv = generate_sample_csv()
    return render_template(
        "teacher/bulk_import.html",
        groups=groups,
        sample_csv=sample_csv,
    )


@teacher_bp.route("/students/bulk-import/sample")
@login_required
def download_sample_csv():
    """Download sample CSV template."""
    from flask import Response
    from services.bulk_import_service import generate_sample_csv

    require_teacher_or_admin()

    csv_content = generate_sample_csv()

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment;filename=student_import_template.csv"
        },
    )


# ============================================================================
# END BULK IMPORT ROUTES
# ============================================================================


# ============================================================================
# ASSIGNMENT TEMPLATE ROUTES
# ============================================================================


@teacher_bp.route("/templates")
@login_required
def templates():
    """List all assignment templates."""
    from services.template_service import (
        get_templates_by_organization,
        get_template_domains,
    )

    require_teacher_or_admin()

    all_templates = get_templates_by_organization(current_user.organization_id)

    # Add domain info to each template
    template_data = []
    for template in all_templates:
        domains = get_template_domains(template.id)
        template_data.append(
            {
                "template": template,
                "domains": domains,
                "domain_count": len(domains),
            }
        )

    return render_template("teacher/templates.html", template_data=template_data)


@teacher_bp.route("/templates/create", methods=["GET", "POST"])
@login_required
def create_template():
    """Create a new assignment template."""
    from services.template_service import create_template as create_template_service
    from services.domain_service import get_visible_domains

    require_teacher_or_admin()

    # Get available domains
    available_domains = get_visible_domains(
        current_user.id, current_user.organization_id
    )

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        domain_ids = request.form.getlist("domain_ids", type=int)

        try:
            template = create_template_service(
                name=name,
                domain_ids=domain_ids,
                organization_id=current_user.organization_id,
                created_by_id=current_user.id,
            )
            flash(f"Template '{template.name}' created successfully!", "success")
            return redirect(url_for("teacher.templates"))
        except ValueError as e:
            flash(str(e), "error")

    return render_template(
        "teacher/create_template.html",
        available_domains=available_domains,
    )


@teacher_bp.route("/templates/<int:template_id>/delete", methods=["POST"])
@login_required
def delete_template(template_id):
    """Delete an assignment template."""
    from services.template_service import get_template_by_id, delete_template as delete

    require_teacher_or_admin()

    template = get_template_by_id(template_id)
    if not template or template.organization_id != current_user.organization_id:
        flash("Template not found", "error")
        return redirect(url_for("teacher.templates"))

    try:
        name = template.name
        delete(template_id)
        flash(f"Template '{name}' deleted", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("teacher.templates"))


# ============================================================================
# END ASSIGNMENT TEMPLATE ROUTES
# ============================================================================

"""Analytics blueprint for dashboard and data exports."""

from flask import Blueprint, render_template, jsonify, Response, abort
from flask_login import current_user, login_required

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")


def require_teacher_or_admin():
    """Check if current user is teacher or admin, abort if not."""
    if not current_user.is_authenticated or current_user.role not in [
        "teacher",
        "admin",
    ]:
        abort(403)


@analytics_bp.route("/dashboard")
@login_required
def dashboard():
    """Main analytics dashboard with charts."""
    from services.analytics_service import (
        get_class_summary_stats,
        get_at_risk_students,
        get_class_completion_rates,
        get_domain_difficulty_comparison,
    )

    require_teacher_or_admin()

    org_id = current_user.organization_id

    # Get summary stats
    summary = get_class_summary_stats(org_id)

    # Get at-risk students
    at_risk = get_at_risk_students(org_id)

    # Get completion rates
    completion_rates = get_class_completion_rates(org_id)

    # Get domain difficulty
    domain_difficulty = get_domain_difficulty_comparison(org_id)

    return render_template(
        "analytics/dashboard.html",
        summary=summary,
        at_risk=at_risk,
        completion_rates=completion_rates,
        domain_difficulty=domain_difficulty,
    )


@analytics_bp.route("/api/class-progress")
@login_required
def api_class_progress():
    """API endpoint for class progress time series data."""
    from services.analytics_service import get_class_progress_over_time

    require_teacher_or_admin()

    org_id = current_user.organization_id
    data = get_class_progress_over_time(org_id, days=30)

    return jsonify(data)


@analytics_bp.route("/api/activity-heatmap")
@login_required
def api_activity_heatmap():
    """API endpoint for activity heatmap data."""
    from services.analytics_service import get_activity_heatmap

    require_teacher_or_admin()

    org_id = current_user.organization_id
    data = get_activity_heatmap(org_id, days=14)

    return jsonify(data)


@analytics_bp.route("/api/at-risk")
@login_required
def api_at_risk():
    """API endpoint for at-risk students."""
    from services.analytics_service import get_at_risk_students

    require_teacher_or_admin()

    org_id = current_user.organization_id
    at_risk = get_at_risk_students(org_id)

    # Serialize for JSON
    result = []
    for student in at_risk:
        result.append(
            {
                "student_id": student["student_id"],
                "name": student["name"],
                "email": student["email"],
                "reasons": student["reasons"],
                "last_active": (
                    student["last_active"].isoformat()
                    if student["last_active"]
                    else None
                ),
            }
        )

    return jsonify(result)


@analytics_bp.route("/api/completion-rates")
@login_required
def api_completion_rates():
    """API endpoint for domain completion rates."""
    from services.analytics_service import get_class_completion_rates

    require_teacher_or_admin()

    org_id = current_user.organization_id
    data = get_class_completion_rates(org_id)

    return jsonify(data)


@analytics_bp.route("/api/domain-difficulty")
@login_required
def api_domain_difficulty():
    """API endpoint for domain difficulty comparison."""
    from services.analytics_service import get_domain_difficulty_comparison

    require_teacher_or_admin()

    org_id = current_user.organization_id
    data = get_domain_difficulty_comparison(org_id)

    return jsonify(data)


@analytics_bp.route("/export/csv")
@login_required
def export_csv():
    """Download CSV export of student progress."""
    from services.analytics_service import export_student_progress_csv

    require_teacher_or_admin()

    org_id = current_user.organization_id
    csv_content = export_student_progress_csv(org_id)

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment;filename=student_progress_export.csv"
        },
    )


@analytics_bp.route("/student/<int:student_id>")
@login_required
def student_analytics(student_id):
    """Individual student analytics view."""
    from models import User, Attempt
    from services.domain_service import get_user_domains
    from services.progress_service import (
        get_student_domain_progress,
        get_questions_answered_today,
        get_total_time_spent,
        format_time_spent,
        is_domain_complete,
    )
    from services.streak_service import get_streak_info
    from datetime import datetime, timedelta

    require_teacher_or_admin()

    student = User.query.get(student_id)
    if not student or student.organization_id != current_user.organization_id:
        abort(404)

    # Get domain progress
    assigned_domains = get_user_domains(student_id)
    domain_progress = []
    for domain in assigned_domains:
        progress = get_student_domain_progress(student_id, domain.id)
        if progress:
            progress["is_complete"] = is_domain_complete(student_id, domain.id)
        domain_progress.append(
            {
                "domain": domain,
                "progress": progress,
            }
        )

    # Get engagement metrics
    questions_today = get_questions_answered_today(student_id)
    total_time = get_total_time_spent(student_id)
    formatted_time = format_time_spent(total_time)
    total_questions = Attempt.query.filter_by(user_id=student_id).count()
    total_correct = Attempt.query.filter_by(user_id=student_id, correct=True).count()
    accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0

    # Get streak info
    streak_info = get_streak_info(student_id)

    # Get activity over last 7 days
    activity_by_day = []
    for i in range(6, -1, -1):
        day = datetime.utcnow() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

        count = Attempt.query.filter(
            Attempt.user_id == student_id,
            Attempt.timestamp >= day_start,
            Attempt.timestamp <= day_end,
        ).count()

        activity_by_day.append(
            {
                "date": day.strftime("%m/%d"),
                "count": count,
            }
        )

    return render_template(
        "analytics/student_analytics.html",
        student=student,
        domain_progress=domain_progress,
        questions_today=questions_today,
        formatted_time=formatted_time,
        total_questions=total_questions,
        total_correct=total_correct,
        accuracy=round(accuracy, 1),
        streak_info=streak_info,
        activity_by_day=activity_by_day,
    )

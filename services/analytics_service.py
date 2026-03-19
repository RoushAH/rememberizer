"""Analytics service for data aggregation and insights."""

from datetime import datetime, timedelta, date
from sqlalchemy import func
from models import (
    db,
    User,
    Domain,
    Fact,
    Attempt,
    FactState,
    DailyProgress,
    UserDomainAssignment,
)
from services.fact_service import get_mastery_status
from services.progress_service import is_domain_complete


def get_class_progress_over_time(org_id, days=30):
    """
    Get time series data for class progress over the last N days.

    Args:
        org_id: Organization ID
        days: Number of days to look back

    Returns:
        dict: Contains dates, questions_answered, questions_correct arrays
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    # Get all students in org
    student_ids = [
        u.id
        for u in User.query.filter_by(
            organization_id=org_id, role="student", is_active=True
        ).all()
    ]

    if not student_ids:
        return {
            "dates": [],
            "questions_answered": [],
            "questions_correct": [],
            "facts_mastered": [],
        }

    # Try to get from DailyProgress table first
    daily_data = (
        db.session.query(
            DailyProgress.date,
            func.sum(DailyProgress.questions_answered).label("total_answered"),
            func.sum(DailyProgress.questions_correct).label("total_correct"),
            func.sum(DailyProgress.facts_mastered).label("total_mastered"),
        )
        .filter(
            DailyProgress.user_id.in_(student_ids),
            DailyProgress.date >= start_date,
            DailyProgress.date <= end_date,
        )
        .group_by(DailyProgress.date)
        .order_by(DailyProgress.date)
        .all()
    )

    # If no daily progress data, compute from Attempts
    if not daily_data:
        daily_data = []
        current_date = start_date
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())

            answered = Attempt.query.filter(
                Attempt.user_id.in_(student_ids),
                Attempt.timestamp >= day_start,
                Attempt.timestamp <= day_end,
            ).count()

            correct = Attempt.query.filter(
                Attempt.user_id.in_(student_ids),
                Attempt.timestamp >= day_start,
                Attempt.timestamp <= day_end,
                Attempt.correct == True,  # noqa: E712
            ).count()

            daily_data.append(
                (current_date, answered, correct, 0)  # Can't easily compute mastered
            )
            current_date += timedelta(days=1)

    # Format for charting
    dates = []
    questions_answered = []
    questions_correct = []
    facts_mastered = []

    # Create a dict for quick lookup
    data_by_date = {d[0]: (d[1], d[2], d[3]) for d in daily_data}

    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.strftime("%m/%d"))
        if current_date in data_by_date:
            questions_answered.append(data_by_date[current_date][0] or 0)
            questions_correct.append(data_by_date[current_date][1] or 0)
            facts_mastered.append(data_by_date[current_date][2] or 0)
        else:
            questions_answered.append(0)
            questions_correct.append(0)
            facts_mastered.append(0)
        current_date += timedelta(days=1)

    return {
        "dates": dates,
        "questions_answered": questions_answered,
        "questions_correct": questions_correct,
        "facts_mastered": facts_mastered,
    }


def get_domain_difficulty_comparison(org_id):
    """
    Get mastery rates by domain for the organization.

    Args:
        org_id: Organization ID

    Returns:
        list: Dicts with domain_name, mastery_rate, avg_attempts
    """
    # Get all students in org
    students = User.query.filter_by(
        organization_id=org_id, role="student", is_active=True
    ).all()

    if not students:
        return []

    # Get all domains that have assignments in this org
    assigned_domain_ids = (
        db.session.query(UserDomainAssignment.domain_id)
        .join(User, User.id == UserDomainAssignment.user_id)
        .filter(User.organization_id == org_id)
        .distinct()
        .all()
    )
    assigned_domain_ids = [d[0] for d in assigned_domain_ids]

    results = []
    for domain_id in assigned_domain_ids:
        domain = Domain.query.get(domain_id)
        if not domain:
            continue

        facts = Fact.query.filter_by(domain_id=domain_id).all()
        if not facts:
            continue

        total_possible_mastery = 0
        total_mastered = 0
        total_attempts = 0

        for student in students:
            # Check if student has this domain assigned
            assignment = UserDomainAssignment.query.filter_by(
                user_id=student.id, domain_id=domain_id
            ).first()
            if not assignment:
                continue

            total_possible_mastery += len(facts)

            for fact in facts:
                if get_mastery_status(fact.id, student.id):
                    total_mastered += 1

                # Count attempts
                attempts = Attempt.query.filter_by(
                    fact_id=fact.id, user_id=student.id
                ).count()
                total_attempts += attempts

        if total_possible_mastery > 0:
            mastery_rate = (total_mastered / total_possible_mastery) * 100
            avg_attempts = total_attempts / total_possible_mastery
            results.append({
                "domain_name": domain.name,
                "domain_id": domain.id,
                "mastery_rate": round(mastery_rate, 1),
                "avg_attempts": round(avg_attempts, 1),
                "total_facts": len(facts),
            })

    # Sort by mastery rate (lowest first = most difficult)
    results.sort(key=lambda x: x["mastery_rate"])
    return results


def get_at_risk_students(org_id, inactive_days=7, decline_threshold=0.5):
    """
    Identify students who may need attention.

    Categories:
    - Inactive: No activity in the last N days
    - Declining: Accuracy dropping significantly
    - Struggling: Below 50% accuracy in last 20 attempts

    Args:
        org_id: Organization ID
        inactive_days: Days without activity to flag as inactive
        decline_threshold: Accuracy drop threshold

    Returns:
        list: Dicts with student info and risk category
    """
    at_risk = []
    cutoff_date = datetime.utcnow() - timedelta(days=inactive_days)

    students = User.query.filter_by(
        organization_id=org_id, role="student", is_active=True
    ).all()

    for student in students:
        risk_reasons = []

        # Check for inactivity
        recent_attempts = Attempt.query.filter(
            Attempt.user_id == student.id, Attempt.timestamp >= cutoff_date
        ).count()

        if recent_attempts == 0:
            # Check if they have any assignments
            assignments = UserDomainAssignment.query.filter_by(
                user_id=student.id
            ).count()
            if assignments > 0:
                risk_reasons.append("inactive")

        # Check accuracy in last 20 attempts
        recent_attempts_data = (
            Attempt.query.filter_by(user_id=student.id)
            .order_by(Attempt.timestamp.desc())
            .limit(20)
            .all()
        )

        if len(recent_attempts_data) >= 10:
            correct = sum(1 for a in recent_attempts_data if a.correct)
            accuracy = correct / len(recent_attempts_data)

            if accuracy < 0.5:
                risk_reasons.append("struggling")

            # Check for decline (compare first half vs second half)
            if len(recent_attempts_data) >= 20:
                first_half = recent_attempts_data[:10]
                second_half = recent_attempts_data[10:]

                first_accuracy = sum(1 for a in first_half if a.correct) / 10
                second_accuracy = sum(1 for a in second_half if a.correct) / 10

                if first_accuracy - second_accuracy > decline_threshold:
                    risk_reasons.append("declining")

        if risk_reasons:
            at_risk.append({
                "student": student,
                "student_id": student.id,
                "name": student.get_full_name(),
                "email": student.email,
                "reasons": risk_reasons,
                "last_active": student.last_active,
            })

    return at_risk


def get_class_completion_rates(org_id):
    """
    Get completion percentage for each domain across the class.

    Args:
        org_id: Organization ID

    Returns:
        list: Dicts with domain_name, completion_rate, completed_count, total_students
    """
    students = User.query.filter_by(
        organization_id=org_id, role="student", is_active=True
    ).all()

    if not students:
        return []

    # Get all domains assigned in this org
    assigned_domain_ids = (
        db.session.query(UserDomainAssignment.domain_id)
        .join(User, User.id == UserDomainAssignment.user_id)
        .filter(User.organization_id == org_id)
        .distinct()
        .all()
    )
    assigned_domain_ids = [d[0] for d in assigned_domain_ids]

    results = []
    for domain_id in assigned_domain_ids:
        domain = Domain.query.get(domain_id)
        if not domain:
            continue

        completed_count = 0
        students_with_domain = 0

        for student in students:
            assignment = UserDomainAssignment.query.filter_by(
                user_id=student.id, domain_id=domain_id
            ).first()
            if not assignment:
                continue

            students_with_domain += 1
            if is_domain_complete(student.id, domain_id):
                completed_count += 1

        if students_with_domain > 0:
            completion_rate = (completed_count / students_with_domain) * 100
            results.append({
                "domain_name": domain.name,
                "domain_id": domain.id,
                "completion_rate": round(completion_rate, 1),
                "completed_count": completed_count,
                "total_students": students_with_domain,
            })

    # Sort by completion rate
    results.sort(key=lambda x: x["completion_rate"], reverse=True)
    return results


def get_activity_heatmap(org_id, days=14):
    """
    Get activity by day of week and hour for heatmap visualization.

    Args:
        org_id: Organization ID
        days: Number of days to look back

    Returns:
        dict: Contains day_labels, hour_labels, and activity matrix
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    student_ids = [
        u.id
        for u in User.query.filter_by(
            organization_id=org_id, role="student", is_active=True
        ).all()
    ]

    if not student_ids:
        return {
            "day_labels": [],
            "hour_labels": [],
            "activity": [],
        }

    # Initialize activity matrix (7 days x 24 hours)
    activity = [[0 for _ in range(24)] for _ in range(7)]

    attempts = Attempt.query.filter(
        Attempt.user_id.in_(student_ids), Attempt.timestamp >= cutoff_date
    ).all()

    for attempt in attempts:
        day_of_week = attempt.timestamp.weekday()  # 0 = Monday
        hour = attempt.timestamp.hour
        activity[day_of_week][hour] += 1

    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    hour_labels = [f"{h:02d}:00" for h in range(24)]

    return {
        "day_labels": day_labels,
        "hour_labels": hour_labels,
        "activity": activity,
    }


def get_class_summary_stats(org_id):
    """
    Get summary statistics for the class.

    Args:
        org_id: Organization ID

    Returns:
        dict: Summary statistics
    """
    students = User.query.filter_by(
        organization_id=org_id, role="student", is_active=True
    ).all()

    student_ids = [s.id for s in students]

    # Total questions answered
    total_questions = Attempt.query.filter(
        Attempt.user_id.in_(student_ids)
    ).count() if student_ids else 0

    # Total correct
    total_correct = Attempt.query.filter(
        Attempt.user_id.in_(student_ids), Attempt.correct == True  # noqa: E712
    ).count() if student_ids else 0

    # Questions today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    questions_today = Attempt.query.filter(
        Attempt.user_id.in_(student_ids), Attempt.timestamp >= today_start
    ).count() if student_ids else 0

    # Active today (students who answered at least 1 question)
    active_today = 0
    if student_ids:
        active_today = (
            db.session.query(Attempt.user_id)
            .filter(
                Attempt.user_id.in_(student_ids), Attempt.timestamp >= today_start
            )
            .distinct()
            .count()
        )

    # Overall accuracy
    accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0

    return {
        "total_students": len(students),
        "total_questions": total_questions,
        "total_correct": total_correct,
        "questions_today": questions_today,
        "active_today": active_today,
        "accuracy": round(accuracy, 1),
    }


def export_student_progress_csv(org_id):
    """
    Generate CSV content for student progress export.

    Args:
        org_id: Organization ID

    Returns:
        str: CSV content
    """
    import io
    import csv

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Student Name",
        "Email",
        "Total Questions",
        "Correct Answers",
        "Accuracy %",
        "Domains Assigned",
        "Domains Completed",
        "Last Active",
        "Current Streak",
    ])

    students = User.query.filter_by(
        organization_id=org_id, role="student", is_active=True
    ).order_by(User.last_name, User.first_name).all()

    for student in students:
        # Total questions and correct
        total = Attempt.query.filter_by(user_id=student.id).count()
        correct = Attempt.query.filter_by(
            user_id=student.id, correct=True
        ).count()
        accuracy = (correct / total * 100) if total > 0 else 0

        # Domains
        assignments = UserDomainAssignment.query.filter_by(user_id=student.id).all()
        domains_assigned = len(assignments)
        domains_completed = sum(
            1
            for a in assignments
            if is_domain_complete(student.id, a.domain_id)
        )

        # Last active
        last_active = (
            student.last_active.strftime("%Y-%m-%d %H:%M")
            if student.last_active
            else "Never"
        )

        writer.writerow([
            student.get_full_name(),
            student.email,
            total,
            correct,
            f"{accuracy:.1f}",
            domains_assigned,
            domains_completed,
            last_active,
            student.current_streak,
        ])

    return output.getvalue()


def update_daily_progress(user_id, questions_answered=0, questions_correct=0, facts_mastered=0):
    """
    Update or create daily progress record for a user.

    This should be called when a quiz answer is submitted.

    Args:
        user_id: User ID
        questions_answered: Number of questions to add
        questions_correct: Number of correct answers to add
        facts_mastered: Number of facts mastered to add
    """
    today = date.today()

    progress = DailyProgress.query.filter_by(user_id=user_id, date=today).first()

    if progress:
        progress.questions_answered += questions_answered
        progress.questions_correct += questions_correct
        progress.facts_mastered += facts_mastered
    else:
        progress = DailyProgress(
            user_id=user_id,
            date=today,
            questions_answered=questions_answered,
            questions_correct=questions_correct,
            facts_mastered=facts_mastered,
        )
        db.session.add(progress)

    db.session.commit()
    return progress

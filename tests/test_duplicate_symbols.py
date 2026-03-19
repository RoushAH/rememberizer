"""Tests for duplicate field values in quiz questions (Greek Muses scenario)."""

import pytest
from models import Fact, Attempt
from services.fact_service import mark_fact_learned
from quiz_logic import generate_question


def test_muses_domain_has_duplicate_symbols(app, muses_domain, erato_and_terpsichore):
    """Verify the test setup: Erato and Terpsichore both have 'Lyre' symbol."""
    erato, terpsichore = erato_and_terpsichore

    with app.app_context():
        erato_data = erato.get_fact_data()
        terpsichore_data = terpsichore.get_fact_data()

        assert erato_data["symbol"] == "Lyre"
        assert terpsichore_data["symbol"] == "Lyre"
        assert erato.id != terpsichore.id


def test_erato_symbol_quiz_excludes_duplicate(
    app, muses_domain, erato_and_terpsichore, student_user
):
    """Test that quizzing Erato's symbol doesn't include Terpsichore's duplicate 'Lyre' in wrong answers."""
    erato, terpsichore = erato_and_terpsichore

    with app.app_context():
        # Learn Erato
        mark_fact_learned(erato.id, student_user.id)

        # Generate question about Erato's symbol (context=name, quiz=symbol)
        all_facts = Fact.query.filter_by(domain_id=muses_domain.id).all()
        question_data = generate_question(erato, "name", "symbol", all_facts, muses_domain)

        options = question_data["options"]
        correct_answer = question_data["correct_answer"]

        assert correct_answer == "Lyre"

        # Count occurrences of "Lyre" in options
        lyre_count = sum(1 for opt in options if opt == "Lyre")
        assert (
            lyre_count == 1
        ), f"'Lyre' should appear exactly once in options, found {lyre_count} times"


def test_terpsichore_symbol_quiz_excludes_duplicate(
    app, muses_domain, erato_and_terpsichore, student_user
):
    """Test that quizzing Terpsichore's symbol doesn't include Erato's duplicate 'Lyre' in wrong answers."""
    erato, terpsichore = erato_and_terpsichore

    with app.app_context():
        # Learn Terpsichore
        mark_fact_learned(terpsichore.id, student_user.id)

        # Generate question about Terpsichore's symbol (context=name, quiz=symbol)
        all_facts = Fact.query.filter_by(domain_id=muses_domain.id).all()
        question_data = generate_question(terpsichore, "name", "symbol", all_facts, muses_domain)

        options = question_data["options"]
        correct_answer = question_data["correct_answer"]

        assert correct_answer == "Lyre"

        # Count occurrences of "Lyre" in options
        lyre_count = sum(1 for opt in options if opt == "Lyre")
        assert (
            lyre_count == 1
        ), f"'Lyre' should appear exactly once in options, found {lyre_count} times"


def test_both_muses_accept_lyre_as_correct(
    authenticated_student, app, muses_domain, erato_and_terpsichore, student_user
):
    """Test that both Erato and Terpsichore accept 'Lyre' as the correct symbol."""
    erato, terpsichore = erato_and_terpsichore

    with app.app_context():
        mark_fact_learned(erato.id, student_user.id)
        mark_fact_learned(terpsichore.id, student_user.id)

        erato_id = erato.id
        terpsichore_id = terpsichore.id

    # Test Erato
    with authenticated_student.session_transaction() as sess:
        sess["domain_id"] = muses_domain.id
        sess["question_count"] = 0
        sess["pending_quiz_fact_id"] = erato_id

    response = authenticated_student.get("/quiz")
    assert response.status_code == 200

    with authenticated_student.session_transaction() as sess:
        if "symbol" in sess.get("current_field_name", "").lower():
            options = sess["options"]
            correct_answer = sess["correct_answer"]

            # Should be "Lyre"
            assert correct_answer == "Lyre"

            # Find index and answer
            correct_index = options.index(correct_answer)

            # Submit answer
            response = authenticated_student.post(
                "/answer", data={"answer": correct_index}, follow_redirects=False
            )

            # Verify marked as correct
            with app.app_context():
                attempt = (
                    Attempt.query.filter_by(fact_id=erato_id, user_id=student_user.id)
                    .order_by(Attempt.id.desc())
                    .first()
                )
                assert attempt.correct is True

    # Test Terpsichore
    with authenticated_student.session_transaction() as sess:
        sess["domain_id"] = muses_domain.id
        sess["question_count"] = 0
        sess["pending_quiz_fact_id"] = terpsichore_id

    response = authenticated_student.get("/quiz")
    assert response.status_code == 200

    with authenticated_student.session_transaction() as sess:
        if "symbol" in sess.get("current_field_name", "").lower():
            options = sess["options"]
            correct_answer = sess["correct_answer"]

            # Should be "Lyre"
            assert correct_answer == "Lyre"

            # Find index and answer
            correct_index = options.index(correct_answer)

            # Submit answer
            response = authenticated_student.post(
                "/answer", data={"answer": correct_index}, follow_redirects=False
            )

            # Verify marked as correct
            with app.app_context():
                attempt = (
                    Attempt.query.filter_by(
                        fact_id=terpsichore_id, user_id=student_user.id
                    )
                    .order_by(Attempt.id.desc())
                    .first()
                )
                assert attempt.correct is True


def test_multiple_quiz_generations_no_duplicate_in_options(
    app, muses_domain, erato_and_terpsichore, student_user
):
    """Test generating multiple questions to ensure 'Lyre' never appears as both correct and wrong."""
    erato, terpsichore = erato_and_terpsichore

    with app.app_context():
        mark_fact_learned(erato.id, student_user.id)
        mark_fact_learned(terpsichore.id, student_user.id)

        all_facts = Fact.query.filter_by(domain_id=muses_domain.id).all()

        # Generate 20 questions for each muse to test randomization
        for _ in range(20):
            # Test Erato (quiz on symbol field)
            erato_question = generate_question(erato, "name", "symbol", all_facts, muses_domain)
            options = erato_question["options"]
            lyre_count = sum(1 for opt in options if opt == "Lyre")
            assert (
                lyre_count == 1
            ), f"Erato question has {lyre_count} 'Lyre' options"

            # Test Terpsichore (quiz on symbol field)
            terp_question = generate_question(terpsichore, "name", "symbol", all_facts, muses_domain)
            options = terp_question["options"]
            lyre_count = sum(1 for opt in options if opt == "Lyre")
            assert (
                lyre_count == 1
            ), f"Terpsichore question has {lyre_count} 'Lyre' options"


def test_other_muse_fields_unaffected_by_duplicate_symbol(
    app, muses_domain, erato_and_terpsichore, student_user
):
    """Test that duplicate symbols don't affect quizzing on other fields (name, domain)."""
    erato, terpsichore = erato_and_terpsichore

    with app.app_context():
        mark_fact_learned(erato.id, student_user.id)
        mark_fact_learned(terpsichore.id, student_user.id)

        all_facts = Fact.query.filter_by(domain_id=muses_domain.id).all()

        # Generate questions for both muses on different fields
        erato_question = generate_question(erato, "symbol", "name", all_facts, muses_domain)
        terp_question = generate_question(terpsichore, "symbol", "domain", all_facts, muses_domain)

        # Verify questions are valid (have 4 options, correct answer is in options)
        for question in [erato_question, terp_question]:
            assert len(question["options"]) == 4
            assert question["correct_answer"] in question["options"]
            assert 0 <= question["correct_index"] < 4


def test_reverse_direction_erato_accepts_terpsichore(
    authenticated_student, app, muses_domain, erato_and_terpsichore, student_user
):
    """Test reverse direction: Quizzing Erato's name, user selects Terpsichore (should be correct)."""
    erato, terpsichore = erato_and_terpsichore

    with app.app_context():
        mark_fact_learned(erato.id, student_user.id)
        erato_id = erato.id
        domain_id = muses_domain.id

    # Try multiple times to get a question where both Erato and Terpsichore are in the options
    max_attempts = 50
    found_valid_question = False

    for _ in range(max_attempts):
        # Force a specific question type by manipulating session
        with authenticated_student.session_transaction() as sess:
            sess["domain_id"] = domain_id
            sess["question_count"] = 0
            sess["pending_quiz_fact_id"] = erato_id

        # Get question (should ask about Erato)
        response = authenticated_student.get("/quiz")
        assert response.status_code == 200

        with authenticated_student.session_transaction() as sess:
            context_field = sess.get("context_field")
            quiz_field = sess.get("current_field_name")
            options = sess["options"]

            # If this is a reverse question (context=symbol, quiz=name)
            if context_field == "symbol" and quiz_field == "name":
                # Check if both Erato and Terpsichore are in options
                if "Erato" in options and "Terpsichore" in options:
                    found_valid_question = True

                    # Find Terpsichore's index (the "alternate" correct answer)
                    terp_index = options.index("Terpsichore")

                    # Submit Terpsichore as the answer
                    response = authenticated_student.post(
                        "/answer", data={"answer": terp_index}, follow_redirects=False
                    )

                    # Verify marked as CORRECT
                    with app.app_context():
                        attempt = (
                            Attempt.query.filter_by(
                                fact_id=erato_id, user_id=student_user.id
                            )
                            .order_by(Attempt.id.desc())
                            .first()
                        )
                        assert attempt is not None, "Attempt should be recorded"
                        assert (
                            attempt.correct is True
                        ), "Terpsichore should be accepted as correct for symbol='Lyre'"
                    break

    assert (
        found_valid_question
    ), "Could not generate a question with both Erato and Terpsichore in options after 50 attempts"


def test_reverse_direction_wrong_answer_still_wrong(
    authenticated_student, app, muses_domain, erato_and_terpsichore, student_user
):
    """Test reverse direction: Wrong muse is still marked as wrong."""
    erato, terpsichore = erato_and_terpsichore

    with app.app_context():
        mark_fact_learned(erato.id, student_user.id)
        erato_id = erato.id
        domain_id = muses_domain.id

    with authenticated_student.session_transaction() as sess:
        sess["domain_id"] = domain_id
        sess["question_count"] = 0
        sess["pending_quiz_fact_id"] = erato_id

    response = authenticated_student.get("/quiz")
    assert response.status_code == 200

    with authenticated_student.session_transaction() as sess:
        context_field = sess.get("context_field")
        quiz_field = sess.get("current_field_name")
        options = sess["options"]

        # If this is a reverse question (context=symbol, quiz=name)
        if context_field == "symbol" and quiz_field == "name":
            # Find a wrong answer (a muse that doesn't have symbol="Lyre")
            wrong_muses = [
                opt for opt in options if opt not in ["Erato", "Terpsichore"]
            ]

            if wrong_muses:
                wrong_index = options.index(wrong_muses[0])

                # Submit wrong answer
                response = authenticated_student.post(
                    "/answer", data={"answer": wrong_index}, follow_redirects=False
                )

                # Verify marked as WRONG
                with app.app_context():
                    attempt = (
                        Attempt.query.filter_by(
                            fact_id=erato_id, user_id=student_user.id
                        )
                        .order_by(Attempt.id.desc())
                        .first()
                    )
                    assert attempt is not None, "Attempt should be recorded"
                    assert (
                        attempt.correct is False
                    ), "Wrong muse should be marked incorrect"

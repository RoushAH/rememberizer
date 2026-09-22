"""Tests for fact service functions."""

from models import Fact
from services.fact_service import (
    mark_fact_learned,
    get_out_of_order_facts,
)


def test_get_out_of_order_facts_none_when_sequential(app, student_user, populated_db):
    """Test that sequential learning produces no out-of-order facts."""
    with app.app_context():
        facts = Fact.query.filter_by(domain_id=populated_db.id).order_by(Fact.id).all()

        # Learn first 3 facts in order
        mark_fact_learned(facts[0].id, student_user.id)
        mark_fact_learned(facts[1].id, student_user.id)
        mark_fact_learned(facts[2].id, student_user.id)

        # No out-of-order facts (sequential learning)
        out_of_order = get_out_of_order_facts(populated_db.id, student_user.id)
        assert len(out_of_order) == 0


def test_get_out_of_order_facts_detects_gap(app, student_user, populated_db):
    """Test detection of gap - unlearned fact before learned fact."""
    with app.app_context():
        facts = Fact.query.filter_by(domain_id=populated_db.id).order_by(Fact.id).all()

        # Learn fact 0, 1, 3 (skip fact 2)
        mark_fact_learned(facts[0].id, student_user.id)
        mark_fact_learned(facts[1].id, student_user.id)
        mark_fact_learned(facts[3].id, student_user.id)

        # Fact 2 should be out-of-order (unlearned but fact 3 is learned)
        out_of_order = get_out_of_order_facts(populated_db.id, student_user.id)
        assert len(out_of_order) == 1
        assert out_of_order[0].id == facts[2].id


def test_get_out_of_order_facts_multiple_gaps(app, student_user, populated_db):
    """Test detection of multiple gaps."""
    with app.app_context():
        facts = Fact.query.filter_by(domain_id=populated_db.id).order_by(Fact.id).all()

        # Learn facts 0, 2, 4 (skip 1 and 3)
        mark_fact_learned(facts[0].id, student_user.id)
        mark_fact_learned(facts[2].id, student_user.id)
        mark_fact_learned(facts[4].id, student_user.id)

        # Facts 1 and 3 should be out-of-order
        out_of_order = get_out_of_order_facts(populated_db.id, student_user.id)
        assert len(out_of_order) == 2
        out_of_order_ids = [f.id for f in out_of_order]
        assert facts[1].id in out_of_order_ids
        assert facts[3].id in out_of_order_ids


def test_get_out_of_order_facts_trailing_unlearned_ok(app, student_user, populated_db):
    """Test that trailing unlearned facts are NOT out-of-order."""
    with app.app_context():
        facts = Fact.query.filter_by(domain_id=populated_db.id).order_by(Fact.id).all()

        # Learn first 3 facts, leave rest unlearned
        mark_fact_learned(facts[0].id, student_user.id)
        mark_fact_learned(facts[1].id, student_user.id)
        mark_fact_learned(facts[2].id, student_user.id)

        # No out-of-order facts (trailing unlearned is normal)
        out_of_order = get_out_of_order_facts(populated_db.id, student_user.id)
        assert len(out_of_order) == 0

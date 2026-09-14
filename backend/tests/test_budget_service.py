import pytest

from app.db.models import Budget
from app.services import budget_service


@pytest.fixture()
def grocery_budget(db_session):
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=1000.0))
    db_session.commit()
    return ("grocery", "2026-09")


def test_get_status_returns_data(db_session, grocery_budget):
    category, period = grocery_budget
    status = budget_service.get_status(db_session, category, period)
    assert status.available_amount == 1000.0


def test_has_sufficient_budget_true_when_cost_below_available(db_session, grocery_budget):
    category, period = grocery_budget
    assert budget_service.has_sufficient_budget(db_session, category, period, cost=500.0) is True


def test_has_sufficient_budget_false_when_cost_exceeds_available(db_session, grocery_budget):
    category, period = grocery_budget
    assert budget_service.has_sufficient_budget(db_session, category, period, cost=1500.0) is False

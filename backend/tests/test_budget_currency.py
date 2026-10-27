"""Budget currency: stored beside the amount as an ISO 4217 code, never converted."""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.db.models import PlanModel
from app.db.schema import ensure_schema
from app.db.session import SessionLocal
from tests.test_plans import create_plan, join, ready_plan, set_prefs  # noqa: F401


def get_plan(client, plan):
    response = client.get(
        f"/api/plans/{plan['plan_id']}", headers={"X-Share-Token": plan["share_token"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_plan_saves_and_returns_amount_and_currency_separately(client):
    plan = create_plan(
        client, location="Austin, Texas, United States", budget_per_person=50, budget_currency="USD"
    )
    view = get_plan(client, plan)
    assert view["budget_per_person"] == 50
    assert view["budget_currency"] == "USD"
    with SessionLocal() as db:
        row = db.get(PlanModel, plan["plan_id"])
        assert (row.budget_per_person, row.budget_currency) == (50.0, "USD")


def test_currency_code_is_normalised(client):
    plan = create_plan(client, budget_currency=" gbp ")
    assert get_plan(client, plan)["budget_currency"] == "GBP"


@pytest.mark.parametrize("bad", ["₹", "US", "DOLLAR", "XXX", "", "USD1"])
def test_unsupported_currency_is_rejected(client, bad):
    response = client.post("/api/plans", json={"location": "London", "budget_currency": bad})
    assert response.status_code == 422


def test_omitted_currency_defaults_to_inr(client):
    """Existing API consumers that never send a currency keep working and keep INR."""
    plan = create_plan(client)
    assert get_plan(client, plan)["budget_currency"] == "INR"


def test_amount_validation_is_unchanged(client):
    for amount in (0, -5, 100001):
        response = client.post(
            "/api/plans",
            json={"location": "London", "budget_per_person": amount, "budget_currency": "GBP"},
        )
        assert response.status_code == 422
    assert (
        client.post("/api/plans", json={"location": "London", "budget_currency": "GBP"}).status_code
        == 201
    )


def test_joining_participant_sees_the_plans_currency(client):
    plan = create_plan(
        client, location="London, United Kingdom", budget_per_person=40, budget_currency="GBP"
    )
    assert join(client, plan, "Asha").status_code == 201
    view = get_plan(client, plan)
    assert (view["budget_per_person"], view["budget_currency"]) == (40, "GBP")
    assert len(view["participants"]) == 1


def test_run_carries_currency_without_converting(client):
    plan = create_plan(
        client, location="New York, USA", budget_per_person=75, budget_currency="USD"
    )
    a = join(client, plan, "Asha").json()
    b = join(client, plan, "Ben").json()
    set_prefs(client, plan, a, ["indie rock", "anime"])
    set_prefs(client, plan, b, ["specialty coffee", "illustration"])
    response = client.post(
        f"/api/plans/{plan['plan_id']}/recommendations",
        headers={"X-Share-Token": plan["share_token"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert any("75 USD" in w and "not been checked" in w for w in body["warnings"])
    assert get_plan(client, plan)["budget_currency"] == "USD"  # persisted and untouched by the run


def test_budget_does_not_change_the_options(client):
    """Amount and currency are recorded only; the same group gets the same options either way."""

    def run(**overrides):
        plan = create_plan(client, **overrides)
        a = join(client, plan, "Asha").json()
        b = join(client, plan, "Ben").json()
        set_prefs(client, plan, a, ["indie rock", "anime"])
        set_prefs(client, plan, b, ["specialty coffee", "illustration"])
        r = client.post(
            f"/api/plans/{plan['plan_id']}/recommendations",
            headers={"X-Share-Token": plan["share_token"]},
        )
        return [o["candidate"]["name"] for o in r.json()["options"]]

    assert run(budget_per_person=10, budget_currency="JPY") == run(
        budget_per_person=9000, budget_currency="GBP"
    )


def test_stateless_recommendation_accepts_currency(client):
    base = {
        "location": "London, United Kingdom",
        "budget_per_person": 60,
        "budget_currency": "GBP",
        "participants": [
            {
                "participant_id": "a",
                "display_name": "A",
                "interests": ["jazz"],
                "resolved_interests": [],
            },
            {
                "participant_id": "b",
                "display_name": "B",
                "interests": ["film"],
                "resolved_interests": [],
            },
        ],
    }
    assert client.post("/api/recommendations", json=base).status_code == 200
    assert (
        client.post("/api/recommendations", json={**base, "budget_currency": "BTC"}).status_code
        == 422
    )


# --- legacy databases -------------------------------------------------------------------


@pytest.fixture
def legacy_engine(tmp_path):
    """A database created by the previous release: plans has no budget_currency column."""
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE plans (id VARCHAR(36) PRIMARY KEY, location VARCHAR(160) NOT NULL, "
                "share_token_hash VARCHAR(128) NOT NULL, budget_per_person FLOAT, "
                "status VARCHAR(24) NOT NULL, expires_at DATETIME NOT NULL, "
                "created_at DATETIME NOT NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO plans VALUES ('legacy-1', 'Chennai', 'h', 800, 'created', "
                "'2999-01-01 00:00:00', '2026-01-01 00:00:00')"
            )
        )
    yield engine
    engine.dispose()


def test_existing_plans_gain_the_inr_default_without_data_loss(legacy_engine):
    ensure_schema(legacy_engine)
    assert "budget_currency" in {c["name"] for c in inspect(legacy_engine).get_columns("plans")}
    with Session(legacy_engine) as db:
        plan = db.get(PlanModel, "legacy-1")
        assert (plan.location, plan.budget_per_person, plan.budget_currency) == (
            "Chennai",
            800.0,
            "INR",
        )


def test_schema_upgrade_is_idempotent(legacy_engine):
    ensure_schema(legacy_engine)
    ensure_schema(legacy_engine)  # a second start must be a no-op, not an error
    with legacy_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM plans")).scalar() == 1


def test_legacy_plan_view_documents_the_default(client):
    """A row with no stored currency is served as INR, never null."""
    plan = create_plan(client)
    with SessionLocal() as db:
        db.execute(text("UPDATE plans SET budget_currency = ''"))
        db.commit()
    assert get_plan(client, plan)["budget_currency"] == "INR"

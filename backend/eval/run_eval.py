import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent import scenario_runner
from app.db.base import Base
from app.db.models import PurchaseOrder, Supplier
from app.seed_data import seed

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RESULTS_DIR = Path(__file__).parent / "results"


def _fresh_seeded_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    seed(session)
    # scenario2 fixtures reference a second open PO on SKU-300 that seed() doesn't create by default
    supplier = session.query(Supplier).filter_by(product_sku="SKU-300").first()
    session.add(PurchaseOrder(product_sku="SKU-300", supplier_id=supplier.id, qty=150, status="submitted"))
    session.commit()
    return session


def run_fixture(fixture: dict) -> dict:
    db = _fresh_seeded_session()
    scenario_type = fixture["scenario_type"]

    if scenario_type == "recommendation_review":
        agent_run = scenario_runner.execute_recommendation_review(db, **fixture["input"])
    elif scenario_type == "supplier_shortfall":
        agent_run = scenario_runner.execute_supplier_shortfall(db, **fixture["input"])
    else:
        raise ValueError(f"Unknown scenario_type: {scenario_type}")

    decision = agent_run.decision
    called_tools = {entry["tool"] for entry in agent_run.tool_call_log}
    expect = fixture["expect"]

    checks = {
        "decision_in_expected_set": decision["decision"] in expect["decision_in"],
        "required_tools_called": set(expect["must_call_tools"]).issubset(called_tools),
    }
    if expect["validator_is_valid"] is not None and agent_run.validator_verdict is not None:
        checks["validator_matches_expectation"] = agent_run.validator_verdict["is_valid"] == expect["validator_is_valid"]

    passed = all(checks.values())
    return {
        "name": fixture["name"],
        "passed": passed,
        "checks": checks,
        "decision": decision,
        "tool_call_log": agent_run.tool_call_log,
        "validator_verdict": agent_run.validator_verdict,
    }


def main() -> int:
    RESULTS_DIR.mkdir(exist_ok=True)
    fixtures = [json.loads(p.read_text()) for p in sorted(FIXTURES_DIR.glob("*.json"))]

    results = []
    for fixture in fixtures:
        print(f"Running {fixture['name']}...")
        result = run_fixture(fixture)
        results.append(result)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = RESULTS_DIR / f"eval_run_{timestamp}.json"
    output_path.write_text(json.dumps(results, indent=2, default=str))

    print("\n%-40s %s" % ("Fixture", "Result"))
    print("-" * 55)
    all_passed = True
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        all_passed = all_passed and result["passed"]
        print("%-40s %s" % (result["name"], status))
        if not result["passed"]:
            print(f"    checks: {result['checks']}")
            print(f"    decision: {result['decision']}")

    print(f"\nTranscripts written to {output_path}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

"""API tests for multi-stage applications (SPEC.md §4.3 "Многоэтапность", service A;
docs/IMPLEMENTATION_PLAN.md §7 "approval этапа I открывает этап II").

Full life cycle: draft -> fill stage I -> submit stage I (application number assigned,
stage I locked, stage II still closed) -> admin walks the status to the
indicative-approval status (opens stage II, advances `checkpoint`) -> fill + submit
stage II (same number, terminal status). Plus a regression check that a single-stage
service still behaves exactly as before this feature.

Deliberately keyword-free like test_control_cases.py (SPEC.md §0 disqualification
clause / `make lint-hardcode`): the two-stage control case is addressed only by its
fixture file name and slug (the slug itself is not one of the forbidden domain nouns);
any option value that might contain one of those nouns is read out of the loaded
fixture JSON at runtime instead of being typed into this file's source.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.models import UserRole
from app.seed.control_cases import run_control_cases
from tests.conftest import build_definition_json, seed_organization, seed_service, seed_user

pytestmark = pytest.mark.asyncio(loop_scope="session")

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "app" / "seed" / "fixtures"
CASE_A_FILE = "control_case_a.json"
CASE_A_SLUG = "wagons-leasing"
NUMBER_RE = re.compile(r"^EPPB-\d{4}-\d{6}$")


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _headers(user) -> dict:
    return {"X-User-Id": str(user.id)}


def _step(definition: dict, stage_key: str, step_key: str) -> dict:
    stage = next(s for s in definition["stages"] if s["key"] == stage_key)
    return next(s for s in stage["steps"] if s["key"] == step_key)


def _field(step: dict, key: str) -> dict:
    return next(f for f in step["fields"] if f["key"] == key)


async def _service_id(client, slug: str) -> str:
    response = await client.get("/api/v1/services")
    item = next(row for row in response.json() if row["slug"] == slug)
    return item["id"]


def _stage_one_payload(fixture: dict) -> dict:
    """A fully-valid stage I data set for the two-stage control case, picking the
    branch (new/ИП/no-subsidy) that keeps the other conditionally-required stage I
    fields closed, same combination `test_control_cases.py` uses."""
    deal_step = _step(fixture, "stage-1", "deal_scope")
    condition_new = _field(deal_step, "wagon_condition")["options"][0]
    wagon_type_value = _field(deal_step, "wagon_type")["options"][0]
    applicant_step = _step(fixture, "stage-1", "applicant")
    applicant_type_value = _field(applicant_step, "applicant_type")["options"][0]
    documents_step = _step(fixture, "stage-1", "documents")
    ip_document_key = _field(documents_step, "ip_registration_certificate")["key"]

    unit_count = 10
    unit_price = 5_000_000
    return {
        "applicant_type": applicant_type_value,
        "company_name": "Тестовый заявитель",
        "bin": "123456789012",
        "contact_phone": "+7 700 000 00 00",
        "wagon_condition": condition_new,
        "wagon_type": wagon_type_value,
        "unit_count": unit_count,
        "unit_price": unit_price,
        "advance_percent": 20,
        "lease_term_months": 36,
        "positions": [{"quantity": unit_count, "unit_price": unit_price}],
        "rate_percent": 12,
        "subsidy_program": False,
        "financial_statement_reference": "Отчёт за отчётный период",
        ip_document_key: "Свидетельство о регистрации",
    }


def _stage_two_payload(fixture: dict) -> dict:
    collateral_step = _step(fixture, "stage-2", "collateral")
    collateral_type_value = _field(collateral_step, "collateral_type")["options"][0]
    return {
        "audited_financials_reference": "Аудит №1 за отчётный период",
        "revenue_last_year": 100_000_000,
        "collateral_type": collateral_type_value,
    }


async def _patch(client, headers, application_id, revision, data_delta, checkpoint=None):
    response = await client.patch(
        f"/api/v1/applications/{application_id}/draft",
        json={"data_delta": data_delta, "checkpoint": checkpoint, "expected_revision": revision},
        headers=headers,
    )
    return response


async def _admin_status(client, admin, application_id, target):
    return await client.post(
        f"/api/v1/admin/applications/{application_id}/status",
        json={"target": target},
        headers=_headers(admin),
    )


# ---------------------------------------------------------------------------
# Full two-stage life cycle
# ---------------------------------------------------------------------------


async def test_multistage_full_life_cycle(client, db_session):
    await run_control_cases()
    fixture = _load_fixture(CASE_A_FILE)
    service_id = await _service_id(client, CASE_A_SLUG)

    applicant = await seed_user(db_session, role=UserRole.ENTREPRENEUR)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    headers = _headers(applicant)

    create = await client.post("/api/v1/applications", json={"service_id": service_id}, headers=headers)
    assert create.status_code == 201, create.text
    application_id = create.json()["id"]
    assert create.json()["checkpoint"]["stage_key"] == "stage-1"
    revision = create.json()["revision"]

    # ---- Fill and submit stage I ----
    patch = await _patch(client, headers, application_id, revision, _stage_one_payload(fixture))
    assert patch.status_code == 200, patch.text
    revision = patch.json()["revision"]

    submit_1 = await client.post(f"/api/v1/applications/{application_id}/submit", headers=headers)
    assert submit_1.status_code == 200, submit_1.text
    submit_1_body = submit_1.json()
    number = submit_1_body["number"]
    assert NUMBER_RE.match(number)
    assert submit_1_body["status"] == "submitted"
    assert submit_1_body["timeline"][-1]["stage"] == "stage-1"

    resume_after_stage_1 = await client.get(f"/api/v1/applications/{application_id}/resume", headers=headers)
    assert resume_after_stage_1.status_code == 200
    resume_body = resume_after_stage_1.json()
    assert resume_body["completed_stages"] == ["stage-1"]
    assert resume_body["stage_open"] is False
    assert resume_body["checkpoint"]["stage_key"] == "stage-1"  # not advanced yet — no approval so far

    # Stage II is still closed: PATCH is rejected regardless of what it targets.
    locked = await _patch(
        client, headers, application_id, revision, {"audited_financials_reference": "x"},
        checkpoint={"stage_key": "stage-2"},
    )
    assert locked.status_code == 409, locked.text
    assert locked.json()["code"] == "stage_locked"

    # Submitting again is also rejected (whole application, not just stage II).
    resubmit = await client.post(f"/api/v1/applications/{application_id}/submit", headers=headers)
    assert resubmit.status_code == 409
    assert resubmit.json()["code"] == "application_not_draft"

    # ---- Admin walks the mock BPM status to the approval status ----
    to_review = await _admin_status(client, admin, application_id, "in_review_bpm")
    assert to_review.status_code == 200, to_review.text

    to_approved = await _admin_status(client, admin, application_id, "indicative_approved")
    assert to_approved.status_code == 200, to_approved.text
    assert to_approved.json()["status"] == "indicative_approved"

    resume_after_approval = await client.get(f"/api/v1/applications/{application_id}/resume", headers=headers)
    assert resume_after_approval.status_code == 200
    approval_body = resume_after_approval.json()
    assert approval_body["status"] == "indicative_approved"
    assert approval_body["checkpoint"]["stage_key"] == "stage-2"
    assert approval_body["completed_stages"] == ["stage-1"]
    assert approval_body["stage_open"] is True
    revision = approval_body["revision"]

    # ---- Fill and submit stage II ----
    patch_2 = await _patch(client, headers, application_id, revision, _stage_two_payload(fixture))
    assert patch_2.status_code == 200, patch_2.text
    revision = patch_2.json()["revision"]

    submit_2 = await client.post(f"/api/v1/applications/{application_id}/submit", headers=headers)
    assert submit_2.status_code == 200, submit_2.text
    submit_2_body = submit_2.json()
    assert submit_2_body["number"] == number  # never reassigned
    assert submit_2_body["status"] == "financing_approved"
    assert submit_2_body["timeline"][-1]["stage"] == "stage-2"

    resume_final = await client.get(f"/api/v1/applications/{application_id}/resume", headers=headers)
    final_body = resume_final.json()
    assert sorted(final_body["completed_stages"]) == ["stage-1", "stage-2"]
    assert final_body["stage_open"] is False


async def test_stage_two_submit_without_required_fields_returns_422(client, db_session):
    """Stage II now carries its own required fields (SPEC.md §4.3) — submitting it
    unfilled must fail the same way stage I's required fields do."""
    await run_control_cases()
    fixture = _load_fixture(CASE_A_FILE)
    service_id = await _service_id(client, CASE_A_SLUG)

    applicant = await seed_user(db_session, role=UserRole.ENTREPRENEUR)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    headers = _headers(applicant)

    create = await client.post("/api/v1/applications", json={"service_id": service_id}, headers=headers)
    application_id = create.json()["id"]
    revision = create.json()["revision"]

    patch = await _patch(client, headers, application_id, revision, _stage_one_payload(fixture))
    revision = patch.json()["revision"]
    await client.post(f"/api/v1/applications/{application_id}/submit", headers=headers)

    await _admin_status(client, admin, application_id, "in_review_bpm")
    await _admin_status(client, admin, application_id, "indicative_approved")

    submit_2 = await client.post(f"/api/v1/applications/{application_id}/submit", headers=headers)
    assert submit_2.status_code == 422, submit_2.text
    body = submit_2.json()
    assert body["code"] == "validation_failed"
    fields = {e["field"] for e in body["details"]["errors"]}
    assert "audited_financials_reference" in fields


# ---------------------------------------------------------------------------
# Regression: a single-stage service submits exactly as before this feature.
# ---------------------------------------------------------------------------


async def test_single_stage_service_regression(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id, definition=build_definition_json())

    create = await client.post("/api/v1/applications", json={"service_id": str(service_row.service_id)}, headers=_headers(user))
    assert create.status_code == 201, create.text
    application_id = create.json()["id"]
    revision = create.json()["revision"]

    patch = await _patch(client, _headers(user), application_id, revision, {"f1": "ИП Тестов", "amount": 1000})
    assert patch.status_code == 200, patch.text
    revision = patch.json()["revision"]

    submit = await client.post(f"/api/v1/applications/{application_id}/submit", headers=_headers(user))
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == "submitted"

    resume = await client.get(f"/api/v1/applications/{application_id}/resume", headers=_headers(user))
    body = resume.json()
    assert body["completed_stages"] == ["main"]
    assert body["stage_open"] is False

    locked = await _patch(client, _headers(user), application_id, revision, {"f2": "x"})
    assert locked.status_code == 409
    assert locked.json()["code"] == "stage_locked"

"""API tests for the two contest control-case Service Definitions (SPEC.md §9,
docs/IMPLEMENTATION_PLAN.md §10 "Этап 5 — контрольные услуги и достоверность").

Deliberately keyword-free (SPEC.md §0 disqualification clause / `make lint-hardcode`):
services are addressed only by fixture file name and slug, never by the domain nouns
the CI grep forbids outside `app/seed` and `docs`. Any option label that might contain
one of those nouns is read out of the loaded fixture JSON at runtime instead of being
typed into this file's source.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import UserRole
from app.schemas.definition import ServiceDefinition as ServiceDefinitionSchema
from app.seed.control_cases import run_control_cases
from tests.conftest import seed_user

# Applied per-function (not module-wide `pytestmark`) because
# `test_fixture_is_valid_against_the_definition_schema` below is synchronous (pure
# schema validation, no server/DB needed) and pytest-asyncio warns on a sync function
# carrying an asyncio mark.
asyncio_test = pytest.mark.asyncio(loop_scope="session")

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "app" / "seed" / "fixtures"
CASE_A_FILE = "control_case_a.json"
CASE_B_FILE = "control_case_b.json"
CASE_A_SLUG = "wagons-leasing"
CASE_B_SLUG = "agro-livestock"
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


def _fields_by_key(screen: dict) -> dict:
    return {f["key"]: f for f in screen["fields"]}


# ---------------------------------------------------------------------------
# Fixtures validate against the DSL schema on their own (no server needed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename", [CASE_A_FILE, CASE_B_FILE])
def test_fixture_is_valid_against_the_definition_schema(filename):
    fixture = _load_fixture(filename)
    ServiceDefinitionSchema.model_validate(fixture)  # raises on any schema/reference error


# ---------------------------------------------------------------------------
# Idempotent load + publish through the public import/publish API -> catalog
# ---------------------------------------------------------------------------


@asyncio_test
async def test_control_cases_are_loaded_and_published_idempotently(client, db_session):
    first = await run_control_cases()
    assert set(first.imported) == {CASE_A_SLUG, CASE_B_SLUG}
    assert set(first.published_this_run) == {CASE_A_SLUG, CASE_B_SLUG}

    response = await client.get("/api/v1/services")
    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json()}
    assert {CASE_A_SLUG, CASE_B_SLUG} <= slugs

    second = await run_control_cases()
    assert second.imported == []
    assert set(second.already_published) == {CASE_A_SLUG, CASE_B_SLUG}
    assert second.published_this_run == []


async def _service_id(client, slug: str) -> str:
    response = await client.get("/api/v1/services")
    item = next(row for row in response.json() if row["slug"] == slug)
    return item["id"]


# ---------------------------------------------------------------------------
# Full draft path through case A: branching, computed formulas, submit.
# Also the "no hardcode" proof: `meta.intake_mapping` (an engine-agnostic, purely
# declarative key) survives the whole import -> publish -> draft -> resume round
# trip unmodified, i.e. nothing in the engine special-cases it.
# ---------------------------------------------------------------------------


@asyncio_test
async def test_case_a_branching_computed_and_submit(client, db_session):
    await run_control_cases()
    fixture = _load_fixture(CASE_A_FILE)
    service_id = await _service_id(client, CASE_A_SLUG)

    applicant = await seed_user(db_session, role=UserRole.ENTREPRENEUR)
    headers = _headers(applicant)

    create = await client.post("/api/v1/applications", json={"service_id": service_id}, headers=headers)
    assert create.status_code == 201, create.text
    application_id = create.json()["id"]
    revision = create.json()["revision"]

    resume = await client.get(f"/api/v1/applications/{application_id}/resume", headers=headers)
    assert resume.status_code == 200
    # Declarative-data proof: this key means nothing to any engine/api file (it is not
    # a field, not a rule target, not a formula ref) yet it rides through untouched.
    assert resume.json()["definition"]["meta"]["intake_mapping"] == fixture["meta"]["intake_mapping"]

    deal_step = _step(fixture, "stage-1", "deal_scope")
    condition_field = _field(deal_step, "wagon_condition")
    condition_new, condition_used = condition_field["options"]
    wagon_type_value = deal_step["fields"][1]["options"][0]

    wagon_details_step = _step(fixture, "stage-1", "wagon_details")
    documents_step = _step(fixture, "stage-1", "documents")
    applicant_step = _step(fixture, "stage-1", "applicant")
    applicant_type_field = _field(applicant_step, "applicant_type")
    applicant_type_value = applicant_type_field["options"][0]
    ip_document_key = _field(documents_step, "ip_registration_certificate")["key"]

    async def patch(data_delta, checkpoint=None):
        nonlocal revision
        response = await client.patch(
            f"/api/v1/applications/{application_id}/draft",
            json={"data_delta": data_delta, "checkpoint": checkpoint, "expected_revision": revision},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        revision = body["revision"]
        return body

    screen_key = wagon_details_step["fields"][0]["key"]
    checkpoint = {"stage_key": "stage-1", "step_key": "wagon_details", "screen_key": screen_key}

    # Branching field, way 1: "new" condition -> only the new-only field is visible.
    body = await patch({"wagon_condition": condition_new}, checkpoint)
    visible = _fields_by_key(body["screen"])
    assert visible["warranty_period_months"]["visible"] is True
    assert visible["manufacture_year"]["visible"] is False
    assert visible["inspection_report_number"]["visible"] is False

    # Branching field, way 2: "used" condition -> the visible field set flips.
    body = await patch({"wagon_condition": condition_used})
    visible = _fields_by_key(body["screen"])
    assert visible["warranty_period_months"]["visible"] is False
    assert visible["manufacture_year"]["visible"] is True
    assert visible["manufacture_year"]["required"] is True
    assert visible["inspection_report_number"]["visible"] is True

    # Back to "new" so the final submit below does not also need the used-only fields.
    await patch({"wagon_condition": condition_new})

    unit_count = 10
    unit_price = 5_000_000
    advance_percent = 20
    lease_term_months = 36
    rate_percent = 12

    body = await patch(
        {
            "applicant_type": applicant_type_value,
            "company_name": "Тестовый заявитель",
            "bin": "123456789012",
            "contact_phone": "+7 700 000 00 00",
            "wagon_type": wagon_type_value,
            "unit_count": unit_count,
            "unit_price": unit_price,
            "advance_percent": advance_percent,
            "lease_term_months": lease_term_months,
            "positions": [{"quantity": unit_count, "unit_price": unit_price}],
            "rate_percent": rate_percent,
            "subsidy_program": False,
            "financial_statement_reference": "Отчёт за отчётный период",
            ip_document_key: "Свидетельство о регистрации",
        }
    )

    computed = body["screen"]["computed"]
    total_cost = Decimal(unit_count) * Decimal(unit_price)
    advance_amount = (total_cost * Decimal(advance_percent) / Decimal(100)).quantize(Decimal(1))
    financing_amount = total_cost - advance_amount
    rate = Decimal(rate_percent) / Decimal(100) / Decimal(12)
    factor = (1 + rate) ** lease_term_months
    monthly_payment = financing_amount * rate * factor / (factor - 1)

    assert Decimal(computed["total_cost"]) == total_cost
    assert Decimal(computed["advance_amount"]) == advance_amount
    assert Decimal(computed["financing_amount"]) == financing_amount
    assert Decimal(computed["monthly_payment"]) == monthly_payment

    submit = await client.post(f"/api/v1/applications/{application_id}/submit", headers=headers)
    assert submit.status_code == 200, submit.text
    submitted = submit.json()
    assert NUMBER_RE.match(submitted["number"])
    assert submitted["status"] == "submitted"


# ---------------------------------------------------------------------------
# Case B: applicant-type/purpose branching + its own computed formula + submit.
# ---------------------------------------------------------------------------


@asyncio_test
async def test_case_b_branching_computed_and_submit(client, db_session):
    await run_control_cases()
    fixture = _load_fixture(CASE_B_FILE)
    service_id = await _service_id(client, CASE_B_SLUG)

    applicant = await seed_user(db_session, role=UserRole.ENTREPRENEUR)
    headers = _headers(applicant)

    create = await client.post("/api/v1/applications", json={"service_id": service_id}, headers=headers)
    assert create.status_code == 201, create.text
    application_id = create.json()["id"]
    revision = create.json()["revision"]

    applicant_step = _step(fixture, "stage-1", "applicant")
    applicant_type_value = _field(applicant_step, "applicant_type")["options"][1]  # "ИП" по фикстуре

    farm_step = _step(fixture, "stage-1", "farm")
    region_value = _field(farm_step, "region")["options"][0]
    land_use_value = _field(farm_step, "land_use_right")["options"][0]

    livestock_step = _step(fixture, "stage-1", "livestock")
    livestock_type_value = _field(livestock_step, "livestock_type")["options"][0]

    purpose_step = _step(fixture, "stage-1", "purpose")
    purpose_field = _field(purpose_step, "funding_purpose")
    purchase_value, construction_value, _working_capital_value = purpose_field["options"]

    purpose_details_step = _step(fixture, "stage-1", "purpose_details")
    documents_step = _step(fixture, "stage-1", "documents")
    ip_document_key = _field(documents_step, "ip_registration_certificate")["key"]

    async def patch(data_delta, checkpoint=None):
        nonlocal revision
        response = await client.patch(
            f"/api/v1/applications/{application_id}/draft",
            json={"data_delta": data_delta, "checkpoint": checkpoint, "expected_revision": revision},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        revision = body["revision"]
        return body

    screen_key = purpose_details_step["fields"][0]["key"]
    checkpoint = {"stage_key": "stage-1", "step_key": "purpose_details", "screen_key": screen_key}

    # Branching field, way 1: "purchase" purpose -> only the purchase-only field required.
    body = await patch({"funding_purpose": purchase_value}, checkpoint)
    visible = _fields_by_key(body["screen"])
    assert visible["purchase_average_price"]["visible"] is True
    assert visible["construction_object_type"]["visible"] is False
    assert visible["working_capital_purpose"]["visible"] is False

    # Branching field, way 2: "construction" purpose -> the visible field set flips.
    body = await patch({"funding_purpose": construction_value})
    visible = _fields_by_key(body["screen"])
    assert visible["purchase_average_price"]["visible"] is False
    assert visible["construction_object_type"]["visible"] is True
    assert visible["construction_object_type"]["required"] is True

    # Back to "purchase" so the final submit only needs one purpose-detail field.
    await patch({"funding_purpose": purchase_value})

    requested_amount = 5_000_000
    collateral_value = 1_000_000

    body = await patch(
        {
            "applicant_type": applicant_type_value,
            "applicant_name": "Тестовое хозяйство",
            "bin_iin": "123456789012",
            "contact_phone": "+7 700 000 00 00",
            "region": region_value,
            "district": "Тестовый район",
            "land_area_hectares": 50,
            "land_use_right": land_use_value,
            "livestock_type": livestock_type_value,
            "livestock_positions": [{"count": 20}],
            "funding_purpose": purchase_value,
            "requested_amount": requested_amount,
            "purchase_average_price": 250_000,
            "collateral_value": collateral_value,
            "has_state_subsidy_support": False,
            "land_ownership_confirmation": "Акт на землю №1",
            ip_document_key: "Свидетельство о регистрации",
        }
    )

    computed = body["screen"]["computed"]
    expected_ratio = (Decimal(collateral_value) / Decimal(requested_amount)).quantize(Decimal("0.01"))
    assert Decimal(computed["collateral_coverage_ratio"]) == expected_ratio

    submit = await client.post(f"/api/v1/applications/{application_id}/submit", headers=headers)
    assert submit.status_code == 200, submit.text
    submitted = submit.json()
    assert NUMBER_RE.match(submitted["number"])
    assert submitted["status"] == "submitted"

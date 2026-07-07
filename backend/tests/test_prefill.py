"""Tests for the PREFILL-by-BIN contract (SPEC.md §4.3 "Предзаполнение из mock-ГБД ЮЛ
по БИН", "Обязательное расширение" §1 "Ничего не спрашиваем, если можем узнать сами").

Covers three layers:
  (a) `app.schemas.definition.FieldBase` accepts `prefill`/`hint` and round-trips them
      through export/import (JSON <-> Pydantic).
  (b) `app.engine.runtime.render()` / `app.api.screen.safe_render()` carry `prefill`/
      `hint` into the screen contract fields the frontend actually receives — without
      this the frontend has no way to know which field is the BIN trigger and which
      fields are auto-fill targets.
  (c) The two contest control-case fixtures and the two neutral demo services (SPEC.md
      §6 item 3) use the convention consistently: the BIN field carries
      `"prefill": "gbd_ul.lookup"`, the company-name field carries
      `"prefill": "gbd_ul.name"`, and both demo services import cleanly with these
      values intact.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.screen import resolve_indices, safe_render
from app.engine.runtime import render
from app.schemas.definition import ServiceDefinition
from app.seed.data import DEMO_SERVICES

pytestmark_async = pytest.mark.asyncio(loop_scope="session")

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "app" / "seed" / "fixtures"


def _definition(**field_overrides) -> ServiceDefinition:
    field = {"key": "bin", "label": "БИН", "type": "text", "required": True}
    field.update(field_overrides)
    source = {
        "service_id": "prefill-demo",
        "meta": {"title": "Prefill Demo"},
        "statuses": ["draft"],
        "stages": [
            {
                "key": "stage",
                "title": "Stage",
                "steps": [
                    {
                        "key": "step",
                        "title": "Step",
                        "fields": [
                            field,
                            {"key": "plain", "label": "Plain field", "type": "text"},
                        ],
                    }
                ],
            }
        ],
    }
    return ServiceDefinition.model_validate(source)


# ---------------------------------------------------------------------------
# (a) schema accepts prefill/hint, round-trips, and extra="forbid" still rejects junk
# ---------------------------------------------------------------------------


def test_field_schema_accepts_prefill_and_hint():
    item = _definition(prefill="gbd_ul.lookup", hint="Введите БИН")
    field = item.stages[0].steps[0].fields[0]
    assert field.prefill == "gbd_ul.lookup"
    assert field.hint == "Введите БИН"


def test_field_prefill_and_hint_default_to_none():
    item = _definition()
    field = item.stages[0].steps[0].fields[0]
    assert field.prefill is None
    assert field.hint is None


def test_export_import_round_trip_preserves_prefill_and_hint():
    item = _definition(prefill="gbd_ul.lookup", hint="Введите БИН")
    dumped = item.model_dump_json()
    restored = ServiceDefinition.model_validate_json(dumped)
    assert restored == item
    restored_field = restored.stages[0].steps[0].fields[0]
    assert restored_field.prefill == "gbd_ul.lookup"
    assert restored_field.hint == "Введите БИН"

    # Same round trip through plain dict (as the constructor's import endpoint receives it).
    as_dict = item.model_dump(mode="json")
    assert as_dict["stages"][0]["steps"][0]["fields"][0]["prefill"] == "gbd_ul.lookup"
    assert as_dict["stages"][0]["steps"][0]["fields"][0]["hint"] == "Введите БИН"
    reimported = ServiceDefinition.model_validate(as_dict)
    assert reimported == item


def test_json_schema_export_lists_prefill_and_hint():
    schema = ServiceDefinition.model_json_schema()
    field_defs = {name: body for name, body in schema["$defs"].items() if name.endswith("Field")}
    assert field_defs, "expected at least one *Field definition in the JSON Schema"
    for name, body in field_defs.items():
        assert "prefill" in body["properties"], f"{name} missing prefill"
        assert "hint" in body["properties"], f"{name} missing hint"


# ---------------------------------------------------------------------------
# (b) the renderer/screen contract ferries prefill/hint through to the frontend
# ---------------------------------------------------------------------------


def test_render_screen_carries_prefill_and_hint_per_field():
    item = _definition(prefill="gbd_ul.lookup", hint="Введите БИН")
    screen = render(item, {})
    fields = {f["key"]: f for f in screen["fields"]}

    trigger = fields["bin"]
    assert trigger["prefill"] == "gbd_ul.lookup"
    assert trigger["hint"] == "Введите БИН"

    plain = fields["plain"]
    assert plain["prefill"] is None
    assert plain["hint"] is None


def test_safe_render_degraded_path_still_carries_prefill_and_hint():
    """`app.api.screen.safe_render` degrades to `_render_without_computed` when a
    computed formula's dependency is not filled yet (SPEC.md §4.3 "Многоэтапность").
    The degraded path builds its own field dicts independently of
    `engine.runtime.render()`, so it needs its own prefill/hint coverage."""
    source = {
        "service_id": "prefill-degraded-demo",
        "meta": {"title": "Prefill Degraded Demo"},
        "statuses": ["draft"],
        "stages": [
            {
                "key": "stage",
                "title": "Stage",
                "steps": [
                    {
                        "key": "step",
                        "title": "Step",
                        "fields": [
                            {
                                "key": "bin",
                                "label": "БИН",
                                "type": "text",
                                "prefill": "gbd_ul.lookup",
                                "hint": "Введите БИН",
                            },
                            {
                                "key": "amount",
                                "label": "Сумма",
                                "type": "number",
                            },
                        ],
                    }
                ],
            }
        ],
        "computed": [{"key": "doubled", "expression": {"op": "mul", "args": ["$amount", 2]}}],
    }
    item = ServiceDefinition.model_validate(source)
    indices = {"stage": 0, "step": 0, "screen": 0}
    # No `amount` in data -> the "doubled" computed formula's dependency is missing ->
    # engine.runtime.render() raises ValueError -> safe_render degrades.
    screen = safe_render(item, {}, indices)
    assert screen["validation"] == [
        {"code": "computed_pending", "message": "Расчёты появятся после заполнения нужных полей"}
    ]
    fields = {f["key"]: f for f in screen["fields"]}
    assert fields["bin"]["prefill"] == "gbd_ul.lookup"
    assert fields["bin"]["hint"] == "Введите БИН"


def test_resolve_indices_still_works_alongside_prefill_fields():
    """Sanity check that adding prefill/hint did not disturb screen_key addressing
    (`app.api.screen.resolve_indices`), which walks the same field list."""
    item = _definition(prefill="gbd_ul.lookup", hint="Введите БИН")
    stage_index, step_index, screen_index = resolve_indices(
        item, {"stage_key": "stage", "step_key": "step", "screen_key": "plain"}
    )
    assert (stage_index, step_index, screen_index) == (0, 0, 0)


# ---------------------------------------------------------------------------
# (c) control-case fixtures and demo services use the convention consistently
# ---------------------------------------------------------------------------


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _step(definition: dict, stage_key: str, step_key: str) -> dict:
    stage = next(s for s in definition["stages"] if s["key"] == stage_key)
    return next(s for s in stage["steps"] if s["key"] == step_key)


def _field(step: dict, key: str) -> dict:
    return next(f for f in step["fields"] if f["key"] == key)


@pytest.mark.parametrize(
    "filename,bin_key,name_key",
    [
        ("control_case_a.json", "bin", "company_name"),
        ("control_case_b.json", "bin_iin", "applicant_name"),
    ],
)
def test_control_case_fixture_bin_field_triggers_gbd_ul_lookup(filename, bin_key, name_key):
    fixture = _load_fixture(filename)
    ServiceDefinition.model_validate(fixture)  # still a valid Definition with prefill/hint present

    applicant_step = _step(fixture, "stage-1", "applicant")
    bin_field = _field(applicant_step, bin_key)
    name_field = _field(applicant_step, name_key)

    assert bin_field["prefill"] == "gbd_ul.lookup"
    assert bin_field.get("hint")

    assert name_field["prefill"] == "gbd_ul.name"
    assert name_field.get("hint")


@pytest.mark.parametrize("spec", DEMO_SERVICES, ids=lambda spec: spec["slug"])
def test_demo_service_definition_bin_field_triggers_gbd_ul_lookup(spec):
    definition = ServiceDefinition.model_validate(spec["definition"])
    applicant_step = definition.stages[0].steps[0]
    fields = {f.key: f for f in applicant_step.fields}
    assert fields["bin"].prefill == "gbd_ul.lookup"
    assert fields["company_name"].prefill == "gbd_ul.name"


@pytestmark_async
async def test_demo_service_seed_import_preserves_prefill(db_session):
    """Full loop: (c) "сид demo-услуги с prefill проходит import" — `run_seed()` drives
    the same import path `app.seed.control_cases`/the constructor use, and the stored
    row must still carry the prefill/hint values afterwards."""
    from sqlalchemy import select

    from app.models import ServiceDefinition as ServiceDefinitionRow
    from app.seed import run_seed

    await run_seed()
    for spec in DEMO_SERVICES:
        row = await db_session.scalar(select(ServiceDefinitionRow).where(ServiceDefinitionRow.slug == spec["slug"]))
        assert row is not None
        applicant_step = row.definition["stages"][0]["steps"][0]
        stored_fields = {f["key"]: f for f in applicant_step["fields"]}
        assert stored_fields["bin"]["prefill"] == "gbd_ul.lookup"
        assert stored_fields["company_name"]["prefill"] == "gbd_ul.name"

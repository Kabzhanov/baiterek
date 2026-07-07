"""Exports the Service Definition DSL as JSON Schema (SPEC.md §3.2,
docs/IMPLEMENTATION_PLAN.md §6 "schema_version и экспорт JSON Schema"). Run via
`python -m app.schemas.export`; writes `docs/service-definition.schema.json` so
external tooling and the future constructor UI can validate against the exact contract
`app.schemas.definition.ServiceDefinition` enforces server-side.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.schemas.definition import ServiceDefinition

# backend/app/schemas/export.py -> parents[3] is the repo root (baiterek/).
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "docs" / "service-definition.schema.json"


def export_schema() -> dict:
    return ServiceDefinition.model_json_schema()


def write_schema(path: Path = DEFAULT_OUTPUT) -> Path:
    schema = export_schema()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    output_path = write_schema()
    print(f"wrote {output_path}")

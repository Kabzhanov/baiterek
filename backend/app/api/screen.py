"""Key-based checkpoint addressing on top of the engine's index-based render contract.

`app/engine/runtime.render()` takes/returns positional `{stage, step, screen}` indices
and chunks a step's fields into screens of `SCREEN_SIZE` (see runtime.render — the split
`[fields[i:i+6] ...]` is positional, independent of rule-driven visibility, so a field's
screen membership is stable for a given Definition version). SPEC.md "Обязательное
расширение" §2/§5 requires `applications.checkpoint` to address a screen by
`screen_key` (the key of the screen's first field), not by index, so that dynamic
field/rule changes never strand a saved position. This module is the bridge: it is
engine-adjacent logic that does not belong inside `app/engine/` (out of scope for this
change) but must exist somewhere for the draft/resume/patch endpoints to work.
"""
from __future__ import annotations

from app.engine.rules import effects
from app.engine.runtime import render

SCREEN_SIZE = 6  # must mirror app.engine.runtime.render()'s chunk size


def _screen_chunks(fields: list) -> list[list]:
    return [fields[i : i + SCREEN_SIZE] for i in range(0, len(fields), SCREEN_SIZE)] or [[]]


def resolve_indices(definition, checkpoint: dict | None) -> tuple[int, int, int]:
    """Map a `{stage_key, step_key, screen_key}` checkpoint to the `(stage, step, screen)`
    indices `app.engine.runtime.render()` expects.

    Falls back to the nearest existing position (0) for missing Definitions, stages,
    steps or screens — e.g. after a stale key or an emptied step.
    """
    checkpoint = checkpoint or {}
    stages = definition.stages
    stage_index = next((i for i, s in enumerate(stages) if s.key == checkpoint.get("stage_key")), 0)
    steps = stages[stage_index].steps if stages else []
    step_index = next((i for i, s in enumerate(steps) if s.key == checkpoint.get("step_key")), 0)
    fields = steps[step_index].fields if steps else []
    chunks = _screen_chunks(fields)
    screen_key = checkpoint.get("screen_key")
    screen_index = next(
        (i for i, chunk in enumerate(chunks) if any(f.key == screen_key for f in chunk)),
        0,
    )
    return stage_index, step_index, screen_index


def _render_without_computed(definition, data: dict, stage_index: int, step_index: int, screen_index: int) -> dict:
    """Degraded stand-in for `engine.runtime.render()` used when a computed formula's
    dependency isn't filled in yet (see `safe_render`). Mirrors render()'s field/chunk/
    progress shape using only `engine.rules.effects()` (rules don't touch formulas)."""
    stage = definition.stages[stage_index]
    step = stage.steps[step_index]
    applied, trace = effects(definition.rules, data)
    fields = [
        {
            "key": f.key,
            "type": f.type,
            "label": f.label,
            "visible": applied.get(f.key) != "hide",
            "required": (f.required or applied.get(f.key) == "require") and applied.get(f.key) != "hide",
            "enabled": applied.get(f.key) != "disable",
            "prefill": f.prefill,
            "hint": f.hint,
        }
        for f in step.fields
    ]
    chunks = _screen_chunks(fields)
    screen = min(screen_index, len(chunks) - 1)
    return {
        "stage": stage.key,
        "step": step.key,
        "screen": screen,
        "fields": chunks[screen],
        "computed": {},
        "validation": [
            {"code": "computed_pending", "message": "Расчёты появятся после заполнения нужных полей"}
        ],
        "progress": {"current": step_index + 1, "total": sum(len(s.steps) for s in definition.stages)},
        "explanations": {"rules": trace, "computed": {}},
    }


def safe_render(definition, data: dict, indices: dict) -> dict:
    """`engine.runtime.render()` calls `engine.formulas.evaluate_formula()` for every
    computed field and that raises `ValueError` the moment a dependency is still
    unfilled — which is the *normal* state of an in-progress draft under SPEC.md's
    incremental-save model, not an error condition. Neither `engine.runtime.render()`
    nor `engine.runtime.compute()` catch this (out of scope to change here), so a
    partially-filled draft would otherwise turn every PATCH/resume into a 500. This
    wrapper degrades to `_render_without_computed` instead: the screen still renders
    with correct visibility, just without the not-yet-computable values.
    """
    try:
        return render(definition, data, indices)
    except ValueError:
        return _render_without_computed(definition, data, indices["stage"], indices["step"], indices["screen"])


def to_checkpoint(render_result: dict) -> dict:
    """Build the canonical key-based checkpoint from an `engine.runtime.render()` result."""
    fields = render_result.get("fields") or []
    return {
        "stage_key": render_result["stage"],
        "step_key": render_result["step"],
        "screen_key": fields[0]["key"] if fields else None,
    }

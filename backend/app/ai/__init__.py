"""AI layer (SPEC.md §7 "AI-компонент", §7.3 "Техконтур"; docs/IMPLEMENTATION_PLAN.md §9).

- `app.ai.provider` — the `LLMProvider` interface both implementations satisfy.
- `app.ai.mock_provider` / `app.ai.anthropic_provider` — the two implementations.
- `app.ai.factory` — picks a provider from ENV and enforces the daily call budget.
- `app.ai.generation` — text → Service Definition draft pipeline (§5.3/§7.2).
- `app.ai.intake` — free-text → top-3 published services (§7.1).
- `app.ai.prompts` — versioned prompt templates, one module per AI feature.

Nothing here talks to SQLAlchemy models directly except `app.ai.budget` (reads/writes
`audit_log` for the daily budget counter) and `app.ai.factory` (wires it together) —
everything else is pure/testable without a database.
"""
from __future__ import annotations

from app.ai.provider import LLMProvider, LLMResult

__all__ = ["LLMProvider", "LLMResult"]

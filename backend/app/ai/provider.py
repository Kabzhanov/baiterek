"""`LLMProvider` — the one interface `app.ai.generation` and `app.ai.intake` talk to
(SPEC.md §7.3 "абстрактный LLMProvider интерфейс").

Kept deliberately tiny (one method, two plain strings in, one result out) so that
`MockLLMProvider` (offline/deterministic) and `AnthropicProvider` (real API call) are
fully interchangeable and neither `app.ai.generation` nor `app.ai.intake` needs to know
which one answered a given prompt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResult:
    """Raw text of a single-turn completion, tagged with which provider produced it."""

    text: str
    provider: str


class LLMProvider(Protocol):
    """Structural interface: any object with a matching `name` + `complete` fits."""

    name: str

    async def complete(self, *, system: str, prompt: str) -> LLMResult:
        """Return one completion for `prompt` under `system` instructions.

        Implementations must NOT raise for "the model produced garbage" — that is a
        normal outcome callers (`app.ai.generation`'s retry loop, `app.ai.intake`'s
        keyword fallback) are built to handle. Raising is reserved for the provider
        itself being unusable (network/auth failure), which callers treat as a reason
        to fall back rather than a bug to propagate as a 500.
        """
        ...

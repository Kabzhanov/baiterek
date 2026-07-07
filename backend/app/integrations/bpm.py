"""Mock BPM adapter (SPEC.md §8): "передача заявки во «внутреннюю BPM» дочерней
организации и обратные webhook-статусы (эмулируются из админки или планировщиком).
Архитектурно — через слой «ЕИШ-адаптер»: один интерфейс шины, разные системы за ней.
Ключевой месседж: ЕППБ не заменяет BPM дочек."

`change_status` is the piece the admin endpoint (`app/api/admin.py`,
`POST /admin/applications/{id}/status`) calls to emulate a BPM decision webhook: it
never lets an application move to an arbitrary status, only to one the Service
Definition's `transitions` explicitly allow from the current status
(`app.engine.runtime.transition` — the same state-machine guard `app/api/applications.py`
uses on applicant-driven `submit`).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.engine.runtime import transition
from app.schemas.definition import ServiceDefinition


@dataclass(frozen=True)
class BpmSubmitResult:
    bpm_reference: str
    accepted_at: datetime
    mock: bool = True


@dataclass(frozen=True)
class BpmStatusResult:
    status: str
    changed_at: datetime
    mock: bool = True


class BpmPort(Protocol):
    """Interface a real dochka-BPM adapter must satisfy."""

    async def submit(self, application_id: uuid.UUID) -> BpmSubmitResult: ...

    async def change_status(
        self,
        definition: ServiceDefinition,
        current_status: str,
        target_status: str,
        data: dict,
    ) -> BpmStatusResult: ...


class MockBpmAdapter:
    """Имитация внутренней BPM дочерней организации — не заменяет её, лишь эмулирует
    приём заявки (`submit`) и обратный статус-webhook (`change_status`)."""

    async def submit(self, application_id: uuid.UUID) -> BpmSubmitResult:
        return BpmSubmitResult(
            bpm_reference=f"MOCK-BPM-{uuid.uuid4().hex[:10].upper()}",
            accepted_at=datetime.now(timezone.utc),
        )

    async def change_status(
        self,
        definition: ServiceDefinition,
        current_status: str,
        target_status: str,
        data: dict,
    ) -> BpmStatusResult:
        # Raises ValueError for a transition the Definition does not declare — the
        # caller (app/api/admin.py) turns that into a 422 ApiError.
        new_status = transition(definition, current_status, target_status, data)
        return BpmStatusResult(status=new_status, changed_at=datetime.now(timezone.utc))


__all__ = ["BpmPort", "BpmStatusResult", "BpmSubmitResult", "MockBpmAdapter"]

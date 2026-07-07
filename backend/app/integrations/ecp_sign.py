"""Mock ЭЦП adapter (SPEC.md §8): "имитация подписания ЭЦП НУЦ РК: модалка «выбор
ключа» → к документу прикрепляется signature_meta". No real cryptography happens here
— `algorithm`/`serial_number` are placeholder strings that are never a valid НУЦ РК
certificate, and every result carries `mock: true` so a caller can never mistake this
for a real signature (SPEC.md §8 "честная пометка").
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class SignatureMeta:
    signed_by: str
    signed_at: datetime
    algorithm: str
    serial_number: str
    mock: bool = True


class EcpSignPort(Protocol):
    """Interface a real ЭЦП НУЦ РК adapter must satisfy."""

    def sign(self, application_id: uuid.UUID, signer_label: str) -> SignatureMeta: ...


class MockEcpSignAdapter:
    """Имитация подписания ЭЦП НУЦ РК — не настоящая криптография."""

    def sign(self, application_id: uuid.UUID, signer_label: str) -> SignatureMeta:
        return SignatureMeta(
            signed_by=signer_label,
            signed_at=datetime.now(timezone.utc),
            algorithm="MOCK-GOST34310-2004",
            serial_number=f"MOCK-{uuid.uuid4().hex[:12].upper()}",
        )


__all__ = ["EcpSignPort", "MockEcpSignAdapter", "SignatureMeta"]

"""Mock ЕИШ adapters (SPEC.md §8 "Имитация интеграций").

Each module here implements the interface a *real* connector to the future
government/BPM systems would have to satisfy — `Protocol` classes named `*Port` — plus
a `Mock*Adapter` implementation used until those systems are reachable. `app/api/`
routers depend only on the adapter instances, so swapping a mock for a real
integration later touches one module, not every caller (mirrors the rationale already
documented on `app/api/deps.py` for the mock eGov IDP auth header).

Every mock response is explicitly marked (`mock: true` + a `disclaimer` string) at the
API boundary — SPEC.md §8 "Честная пометка «имитация eGov IDP»" applies to all four
adapters, not just eGov.
"""
from __future__ import annotations

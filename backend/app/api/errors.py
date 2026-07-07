"""Uniform API error envelope: `{code, message, details, trace_id}` (SPEC.md §5,
docs/IMPLEMENTATION_PLAN.md §5 "ошибка {code,message,details,trace_id}").

Routers raise `ApiError`; `app.main` registers the exception handler that attaches
`request.state.trace_id` (set by the trace-id middleware) and serializes the body.
"""
from __future__ import annotations


class ApiError(Exception):
    """Raise from an API route to produce a structured JSON error response.

    `details` must stay JSON-serializable (no ORM objects) since it is passed
    straight to `JSONResponse`.
    """

    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

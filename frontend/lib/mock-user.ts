// Mock auth (SPEC.md §8 "mock eGov IDP"): the backend identifies the caller purely via
// an `X-User-Id` header naming an existing `users.id` (see `backend/app/api/deps.py`).
// Isolated here so swapping in real eGov IDP later only touches this one module.
//
// Resolution order: an operator-set constant (`NEXT_PUBLIC_MOCK_USER_ID`, for pointing
// the stand at a known seeded user) wins if present; otherwise a UUID is generated once
// on first visit and persisted in `localStorage`, so the same browser keeps resuming the
// same drafts across reloads (but not across devices — that is what draft/resume is for).

const STORAGE_KEY = "baiterek.mock_user_id";

function generateUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // RFC 4122 v4 fallback for environments without `crypto.randomUUID` (older browsers).
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getMockUserId(): string {
  const configured = process.env.NEXT_PUBLIC_MOCK_USER_ID;
  if (configured) return configured;
  if (typeof window === "undefined") {
    // Server-rendered paths never call the draft API directly (see application-api.ts
    // module comment) — this branch only guards against accidental SSR use.
    return "server";
  }
  const existing = window.localStorage.getItem(STORAGE_KEY);
  if (existing) return existing;
  const created = generateUuid();
  window.localStorage.setItem(STORAGE_KEY, created);
  return created;
}

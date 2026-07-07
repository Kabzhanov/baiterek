// Client for the draft/checkpoint API (SPEC.md §5, "Обязательное расширение"):
// POST /applications, PATCH /applications/{id}/draft, GET /applications/{id}/resume,
// POST /applications/{id}/submit, plus GET /services/{slug} to resolve a slug to the
// `service_id` the create endpoint expects. See `backend/app/api/contracts.py` for the
// exact response models this mirrors.
//
// Deliberately NOT built on `lib/api.ts`'s `request()` helper: that helper swallows every
// failure and falls back to bundled mock data, which is right for the read-only catalog
// but wrong here — SPEC item 7 requires an honest "стенд недоступен" screen instead of a
// mocked submission. `call()` below always distinguishes "backend unreachable"
// (`BackendUnavailableError`) from "backend answered with an error"
// (`ApplicationApiError`, carrying the structured `{code,message,details,trace_id}` body).
import { getMockUserId } from "./mock-user";
import type {
  ApiErrorBody,
  ApplicationOut,
  Checkpoint,
  DraftPatchOut,
  ResumeOut,
  ServiceSummaryOut,
  SubmitOut,
} from "./application-types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/baiterek/api";

export class BackendUnavailableError extends Error {
  constructor(message = "Стенд временно недоступен") {
    super(message);
    this.name = "BackendUnavailableError";
  }
}

export class ApplicationApiError extends Error {
  status: number;
  body: ApiErrorBody;
  constructor(status: number, body: ApiErrorBody) {
    super(body.message || `API error ${status}`);
    this.name = "ApplicationApiError";
    this.status = status;
    this.body = body;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-User-Id": getMockUserId(),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    // Network failure, DNS error, connection refused — the stand itself is unreachable.
    throw new BackendUnavailableError();
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (!body || typeof body.code !== "string") {
      // A non-JSON error body means we didn't even reach the FastAPI app (e.g. nginx/502) —
      // treat it the same as unreachable rather than showing a garbled error.
      throw new BackendUnavailableError();
    }
    throw new ApplicationApiError(response.status, body as ApiErrorBody);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new BackendUnavailableError();
  }
}

export type PatchDraftPayload = {
  data_delta: Record<string, unknown>;
  checkpoint: Partial<Checkpoint> | null;
  expected_revision: number;
};

export const applicationApi = {
  getService: (slug: string) => call<ServiceSummaryOut>(`/v1/services/${encodeURIComponent(slug)}`),
  createApplication: (serviceId: string) =>
    call<ApplicationOut>("/v1/applications", {
      method: "POST",
      body: JSON.stringify({ service_id: serviceId }),
    }),
  patchDraft: (applicationId: string, payload: PatchDraftPayload) =>
    call<DraftPatchOut>(`/v1/applications/${applicationId}/draft`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  resume: (applicationId: string) => call<ResumeOut>(`/v1/applications/${applicationId}/resume`),
  submit: (applicationId: string) =>
    call<SubmitOut>(`/v1/applications/${applicationId}/submit`, { method: "POST" }),
};

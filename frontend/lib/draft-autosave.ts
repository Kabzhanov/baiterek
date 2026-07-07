// Pure autosave logic for the application wizard (SPEC.md "Обязательное расширение" §2:
// "Автосохранение непрерывное… debounce 800 мс… гарантированное сохранение при переходе
// между экранами"). Kept free of React/DOM/fetch so it can be unit tested directly
// (see application-wizard.test.ts) — all I/O happens through the injected `onFlush`
// callback that the component supplies.

export type FieldDelta = Record<string, unknown>;

export type DebouncedSaver = {
  /** Queue a field edit; coalesces with any not-yet-sent edit and (re)starts the debounce timer. */
  schedule: (delta: FieldDelta) => void;
  /** Remove and return whatever is queued right now, without waiting for the timer. */
  take: () => FieldDelta;
  /** Send whatever is queued immediately (tab hidden, unmount) — a no-op if nothing is pending. */
  flushNow: () => void;
  /** Drop anything queued without saving (used when a request is about to supersede it). */
  cancel: () => void;
  hasPending: () => boolean;
};

/** Debounces field edits into a single coalesced save call. Later edits to the same key
 * win over earlier ones within the same debounce window — this is the same last-write-wins
 * rule the server applies to `data_delta` (`{**application.data, **payload.data_delta}`). */
export function createDebouncedSaver(onFlush: (delta: FieldDelta) => void, delayMs = 800): DebouncedSaver {
  let pending: FieldDelta = {};
  let timer: ReturnType<typeof setTimeout> | null = null;

  function clearTimer() {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function take(): FieldDelta {
    clearTimer();
    const delta = pending;
    pending = {};
    return delta;
  }

  function schedule(delta: FieldDelta) {
    pending = { ...pending, ...delta };
    clearTimer();
    timer = setTimeout(() => onFlush(take()), delayMs);
  }

  function flushNow() {
    if (Object.keys(pending).length === 0 && timer === null) return;
    onFlush(take());
  }

  function cancel() {
    clearTimer();
    pending = {};
  }

  function hasPending() {
    return Object.keys(pending).length > 0;
  }

  return { schedule, take, flushNow, cancel, hasPending };
}

/** After a stale `expected_revision` (409 `revision_conflict`), the edits the applicant made
 * since the last confirmed save must survive — they are reapplied on top of the server's
 * freshly re-fetched authoritative data rather than discarded or silently dropped. Local
 * pending edits win for the keys they touch because they are strictly newer than whatever
 * produced the conflict (SPEC.md §2: a stale write must never clobber a newer one, and
 * symmetrically the applicant's own newest input must never be the thing that gets lost). */
export function mergeAfterConflict(serverData: FieldDelta, pendingLocalDelta: FieldDelta): FieldDelta {
  return { ...serverData, ...pendingLocalDelta };
}

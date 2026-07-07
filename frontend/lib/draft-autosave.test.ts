import { describe, expect, it, vi } from "vitest";
import { createDebouncedSaver, mergeAfterConflict } from "./draft-autosave";

describe("createDebouncedSaver", () => {
  it("coalesces edits made within the debounce window into a single save", () => {
    vi.useFakeTimers();
    const onFlush = vi.fn();
    const saver = createDebouncedSaver(onFlush, 800);

    saver.schedule({ f1: "Ив" });
    vi.advanceTimersByTime(300);
    saver.schedule({ f1: "Иван" });
    vi.advanceTimersByTime(300);
    saver.schedule({ f2: 42 });

    expect(onFlush).not.toHaveBeenCalled();
    vi.advanceTimersByTime(800);

    expect(onFlush).toHaveBeenCalledTimes(1);
    expect(onFlush).toHaveBeenCalledWith({ f1: "Иван", f2: 42 });
    vi.useRealTimers();
  });

  it("take() returns and clears whatever is queued without waiting for the timer, for a forced navigation flush", () => {
    vi.useFakeTimers();
    const onFlush = vi.fn();
    const saver = createDebouncedSaver(onFlush, 800);

    saver.schedule({ f1: "a" });
    const taken = saver.take();

    expect(taken).toEqual({ f1: "a" });
    expect(saver.hasPending()).toBe(false);

    // The debounce timer that would have fired must be cancelled by take(), otherwise the
    // navigation-time save and a stray debounce save would race and double-send.
    vi.advanceTimersByTime(2000);
    expect(onFlush).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("flushNow() is a no-op when nothing is pending", () => {
    const onFlush = vi.fn();
    const saver = createDebouncedSaver(onFlush, 800);
    saver.flushNow();
    expect(onFlush).not.toHaveBeenCalled();
  });
});

describe("mergeAfterConflict", () => {
  it("reapplies the applicant's just-rejected edits on top of the server's authoritative data", () => {
    const serverData = { f1: "old value", f2: "untouched by this session" };
    const pendingLocalDelta = { f1: "what the applicant just typed" };

    const merged = mergeAfterConflict(serverData, pendingLocalDelta);

    expect(merged).toEqual({ f1: "what the applicant just typed", f2: "untouched by this session" });
  });

  it("never drops fields the server has that the local delta doesn't touch", () => {
    const merged = mergeAfterConflict({ a: 1, b: 2, c: 3 }, { b: 99 });
    expect(merged).toEqual({ a: 1, b: 99, c: 3 });
  });
});

import { describe, expect, it } from "vitest";
import { afterDecision, batchPosition, counts, filterCases, lastDecision, startBatch, type Case, type ReviewStatus } from "../model/worklist";

const make = (statuses: ReviewStatus[]): Case[] =>
  statuses.map((status, i) => ({
    id: `sub-${String(i + 1).padStart(3, "0")}`,
    scan: "DCE-MRI",
    slices: 128,
    annotatedBy: "Lesion model v2.1",
    updated: "2026-10-03",
    status,
    note: null,
    reviewedBy: null,
  }));

describe("counts", () => {
  it("counts each status and how many have a decision", () => {
    expect(counts(make(["review", "confirmed", "needs", "review"]))).toEqual({
      review: 2, needs: 1, confirmed: 1, reviewed: 2, total: 4,
    });
  });
});

describe("lastDecision", () => {
  it("gives the latest date among decided cases", () => {
    const cases = make(["confirmed", "review", "needs"]);
    cases[0].updated = "2026-10-20";
    cases[1].updated = "2026-11-01";
    cases[2].updated = "2026-10-25";
    expect(lastDecision(cases)).toBe("2026-10-25");
  });

  it("is null when no case has a decision", () => {
    expect(lastDecision(make(["review"]))).toBeNull();
  });
});

describe("filterCases", () => {
  const cases = make(["review", "confirmed", "review"]);

  it("keeps the cases on a tab", () => {
    expect(filterCases(cases, "review", "").map(c => c.id)).toEqual(["sub-001", "sub-003"]);
    expect(filterCases(cases, "all", "")).toHaveLength(3);
  });

  it("matches the case id, ignoring case and spaces", () => {
    expect(filterCases(cases, "all", " SUB-002 ").map(c => c.id)).toEqual(["sub-002"]);
  });
});

describe("startBatch", () => {
  const cases = make(["confirmed", "review", "review", "needs", "review"]);

  it("takes the first n cases still to review", () => {
    expect(startBatch(cases, 2)).toEqual({ ids: ["sub-002", "sub-003"], total: 2 });
  });

  it("takes only what is left when n is larger", () => {
    expect(startBatch(cases, 10)).toEqual({ ids: ["sub-002", "sub-003", "sub-005"], total: 3 });
  });

  it("starts nothing for n below 1 or nothing to review", () => {
    expect(startBatch(cases, 0)).toBeNull();
    expect(startBatch(make(["confirmed"]), 5)).toBeNull();
  });
});

describe("batchPosition", () => {
  it("counts from 1 as cases are decided", () => {
    expect(batchPosition({ ids: ["a", "b", "c"], total: 3 })).toBe(1);
    expect(batchPosition({ ids: ["c"], total: 3 })).toBe(3);
  });
});

describe("afterDecision", () => {
  it("moves to the next case in the batch", () => {
    const cases = make(["confirmed", "review", "review"]);
    expect(afterDecision(cases, { ids: ["sub-001", "sub-002"], total: 2 }, "sub-001")).toEqual({
      selectedId: "sub-002", batch: { ids: ["sub-002"], total: 2 }, finished: false,
    });
  });

  it("finishes the batch after its last case, staying on that case", () => {
    const cases = make(["confirmed", "review"]);
    expect(afterDecision(cases, { ids: ["sub-001"], total: 2 }, "sub-001")).toEqual({
      selectedId: "sub-001", batch: null, finished: true,
    });
  });

  it("without a batch, moves to the next case to review after the decided one", () => {
    const cases = make(["review", "needs", "review", "review"]);
    expect(afterDecision(cases, null, "sub-002").selectedId).toBe("sub-003");
    expect(afterDecision(cases, null, "sub-004").selectedId).toBe("sub-001");
  });

  it("without a batch, stays put when nothing is left to review", () => {
    expect(afterDecision(make(["confirmed"]), null, "sub-001")).toEqual({
      selectedId: "sub-001", batch: null, finished: false,
    });
  });
});

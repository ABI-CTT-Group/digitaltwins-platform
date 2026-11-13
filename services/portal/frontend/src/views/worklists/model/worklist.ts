// Worklist rules for the frontend-only prototype: which cases show, and where review goes next.
// Pure functions; the store holds the cases and the page holds the batch.

/** A case's review decision; "review" means no decision yet. */
export type ReviewStatus = "review" | "needs" | "confirmed";
export type Tab = ReviewStatus | "all";

/** One subject of the study, reviewed as a unit. One decision per case, shared by the project. */
export interface Case {
  id: string;
  scan: string;
  slices: number;
  /** Who drew the annotation: a model or a person. */
  annotatedBy: string;
  /** ISO date of the last change. */
  updated: string;
  status: ReviewStatus;
  /** What to fix, for a case that needs correction. */
  note: string | null;
  reviewedBy: string | null;
}

/** The cases picked by "Review next N cases"; `ids` still to decide, current case first. */
export interface Batch {
  ids: string[];
  total: number;
}

export const STATUS_LABEL: Record<ReviewStatus, string> = {
  review: "To review",
  needs: "Needs correction",
  confirmed: "Confirmed",
};

export function counts(cases: Case[]) {
  const n = (s: ReviewStatus) => cases.filter(c => c.status === s).length;
  const review = n("review");
  return { review, needs: n("needs"), confirmed: n("confirmed"), reviewed: cases.length - review, total: cases.length };
}

export function filterCases(cases: Case[], tab: Tab, query: string): Case[] {
  const q = query.trim().toLowerCase();
  return cases.filter(c => (tab === "all" || c.status === tab) && c.id.toLowerCase().includes(q));
}

/** The first `n` cases still to review, or null when there is nothing to start. */
export function startBatch(cases: Case[], n: number): Batch | null {
  const ids = cases.filter(c => c.status === "review").slice(0, Math.max(0, Math.floor(n))).map(c => c.id);
  return ids.length ? { ids, total: ids.length } : null;
}

/** 1-based position of the current case within its batch. */
export const batchPosition = (b: Batch) => b.total - b.ids.length + 1;

/** Where to go once `decidedId` has its decision: the batch's next case, or else the next case to
 *  review after it (wrapping round). Stays on the decided case when there is nowhere to go. */
export function afterDecision(cases: Case[], batch: Batch | null, decidedId: string) {
  if (batch) {
    const ids = batch.ids.filter(id => id !== decidedId);
    return ids.length
      ? { selectedId: ids[0], batch: { ids, total: batch.total }, finished: false }
      : { selectedId: decidedId, batch: null, finished: true };
  }
  const at = cases.findIndex(c => c.id === decidedId);
  const next = [...cases.slice(at + 1), ...cases.slice(0, at)].find(c => c.status === "review");
  return { selectedId: next?.id ?? decidedId, batch: null, finished: false };
}

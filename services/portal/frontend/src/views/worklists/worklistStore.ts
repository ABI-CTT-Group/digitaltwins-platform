// The worklist's example cases and the decisions made on them.
// Frontend-only prototype: kept in this browser's localStorage; nothing is sent to a server.
import { defineStore } from "pinia";
import type { Case, ReviewStatus } from "./model/worklist";
import example from "./fixtures/example-cases.json";

/** The one example study; not persisted, so the fixture always names it. */
export const STUDY = example.study;

export const useWorklistStore = defineStore("worklist", {
  state: () => ({
    cases: structuredClone(example.cases) as Case[],
  }),
  actions: {
    /** Record a review decision on one case; one decision per case, shared by the project. */
    decide(id: string, status: Exclude<ReviewStatus, "review">, note: string | null, reviewer: string) {
      const c = this.cases.find(x => x.id === id);
      if (!c) return;
      Object.assign(c, { status, note, reviewedBy: reviewer, updated: new Date().toISOString().slice(0, 10) });
    },
  },
  persist: true,
});

import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";
import { createApp, nextTick } from "vue";
import { STUDY, useWorklistStore } from "../worklistStore";
import { counts } from "../model/worklist";

// Pinia applies plugins only once it is installed in an app, as main.ts does.
const freshPinia = () => {
  const pinia = createPinia().use(piniaPluginPersistedstate);
  createApp({}).use(pinia);
  setActivePinia(pinia);
};

beforeEach(() => {
  localStorage.clear();
  freshPinia();
});

describe("worklistStore", () => {
  it("starts from the example cases", () => {
    const store = useWorklistStore();
    expect(STUDY).toMatchObject({ id: "breast-mri-reading", title: "Breast MRI reading" });
    expect(counts(store.cases)).toEqual({ review: 21, needs: 3, confirmed: 12, reviewed: 15, total: 36 });
  });

  it("records a decision with who made it and when", () => {
    const store = useWorklistStore();
    store.decide("sub-013", "needs", "Misses the lower margin", "Dr A. Reader");
    expect(store.cases.find(c => c.id === "sub-013")).toMatchObject({
      status: "needs", note: "Misses the lower margin", reviewedBy: "Dr A. Reader",
      updated: new Date().toISOString().slice(0, 10),
    });
    store.decide("sub-003", "confirmed", null, "Dr A. Reader");
    expect(store.cases.find(c => c.id === "sub-003")).toMatchObject({ status: "confirmed", note: null });
  });

  it("keeps decisions across a reload", async () => {
    useWorklistStore().decide("sub-013", "confirmed", null, "Dr A. Reader");
    await nextTick();
    freshPinia();
    expect(useWorklistStore().cases.find(c => c.id === "sub-013")?.status).toBe("confirmed");
  });
});

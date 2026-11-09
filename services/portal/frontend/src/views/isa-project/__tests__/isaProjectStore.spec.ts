import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";
import { createApp, nextTick } from "vue";
import { useIsaProjectStore } from "../isaProjectStore";
import { fixtureSource } from "../adapter/isaProjectSource";

// Pinia applies plugins only once it is installed in an app, as main.ts does.
const freshPinia = () => {
  const pinia = createPinia().use(piniaPluginPersistedstate);
  createApp({}).use(pinia);
  setActivePinia(pinia);
};

const upload = async (over: Record<string, unknown> = {}) => {
  const p = await fixtureSource.loadExample("example-breast-pilot");
  return JSON.stringify({ ...p, project: { id: "p-mine", title: "My study plan" }, ...over });
};

beforeEach(() => {
  localStorage.clear();
  freshPinia();
});

describe("isaProjectStore", () => {
  it("seeds the examples once", async () => {
    const store = useIsaProjectStore();
    await Promise.all([store.ensureExamples(), store.ensureExamples()]);
    await store.ensureExamples();
    expect(store.entries.map(e => [e.project.project.id, e.source])).toEqual([
      ["p-breast-pilot", "example"],
    ]);
  });

  it("drops examples that no longer ship, but keeps uploads", async () => {
    const store = useIsaProjectStore();
    const old = JSON.parse(await upload());
    store.entries = [
      { project: { ...old, project: { id: "p-lung", title: "Lung (old example)" } }, source: "example", exampleId: "example-lung" },
      { project: old, source: "upload" },
    ];
    await store.ensureExamples();
    expect(store.entries.map(e => [e.project.project.id, e.source])).toEqual([
      ["p-mine", "upload"], ["p-breast-pilot", "example"],
    ]);
  });

  it("adds an uploaded project, and replaces one with the same project id", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    expect(await store.upload(await upload())).toEqual({ ok: true, projectId: "p-mine" });
    expect(store.has("p-mine")).toBe(true);
    await store.upload(JSON.stringify({ ...JSON.parse(await upload()), project: { id: "p-mine", title: "Renamed" } }));
    expect(store.entries.filter(e => e.project.project.id === "p-mine").map(e => [e.source, e.project.project.title]))
      .toEqual([["upload", "Renamed"]]);
  });

  it("returns the errors of a bad upload and leaves the store as it was", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    const before = JSON.stringify(store.entries);
    const r = await store.upload("{oops");
    expect(r).toEqual({ ok: false, errors: ["The file is not valid JSON."] });
    expect(JSON.stringify(store.entries)).toBe(before);
  });

  it("removes a project and resets an edited example", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    await store.upload(await upload());
    store.remove("p-mine");
    expect(store.has("p-mine")).toBe(false);

    store.study("p-breast-pilot", "s-pilot")!.assays[0].title = "Edited";
    await store.resetExample("p-breast-pilot");
    expect(store.study("p-breast-pilot", "s-pilot")!.assays[0].title).toBe("Assay 1: cohort selection");
  });

  it("finds a study by project and study id", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    expect(store.study("p-breast-pilot", "s-pilot")?.title).toBe("Breast pilot");
    expect(store.study("p-breast-pilot", "nope")).toBeNull();
  });

  it("keeps uploads and edits across a page reload (localStorage)", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    await store.upload(await upload());
    store.study("p-breast-pilot", "s-pilot")!.assays[0].title = "Edited";
    await nextTick();

    freshPinia();
    const reloaded = useIsaProjectStore();
    expect(reloaded.has("p-mine")).toBe(true);
    expect(reloaded.study("p-breast-pilot", "s-pilot")!.assays[0].title).toBe("Edited");
  });
});

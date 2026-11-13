import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";
import { createApp, nextTick } from "vue";
import { useIsaProjectStore } from "../isaProjectStore";
import { fixtureSource } from "../adapter/isaProjectSource";
import { APPROVE_STEP } from "../isaProjectStore";

// Pinia applies plugins only once it is installed in an app, as main.ts does.
const freshPinia = () => {
  const pinia = createPinia().use(piniaPluginPersistedstate);
  createApp({}).use(pinia);
  setActivePinia(pinia);
};

const upload = async (over: Record<string, unknown> = {}) => {
  const p = await fixtureSource.loadExample("example-test-project");
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
      ["p-test-project", "example"],
    ]);
  });

  it("drops examples that no longer ship, such as the retired breast pilot, but keeps uploads", async () => {
    const store = useIsaProjectStore();
    const old = JSON.parse(await upload());
    store.entries = [
      { project: { ...old, project: { id: "p-breast-pilot", title: "Breast pilot (example)" } }, source: "example", exampleId: "example-breast-pilot" },
      { project: old, source: "upload" },
    ];
    await store.ensureExamples();
    expect(store.entries.map(e => [e.project.project.id, e.source])).toEqual([
      ["p-mine", "upload"], ["p-test-project", "example"],
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

  it("adds a bundled project with its new items, and replaces one with the same project id", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    const project = JSON.parse(await upload());
    const bundled = { datasets: [{ id: "ds-new", name: "ds-new", category: "measurements" as const, bundled: { fileCount: 1, bytes: 9 } }], workflows: [], tools: [] };
    store.addBundle(project, bundled);
    store.addBundle({ ...project, project: { id: "p-mine", title: "Renamed" } }, bundled);
    expect(store.entries.filter(e => e.project.project.id === "p-mine").map(e => [e.source, e.project.project.title, e.bundled]))
      .toEqual([["upload", "Renamed", bundled]]);
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

    store.study("p-test-project", "s-test")!.assays[0].title = "Edited";
    await store.resetExample("p-test-project");
    expect(store.study("p-test-project", "s-test")!.assays[0].title).toBe("Test Assay 1: cohort selection");
  });

  it("finds a study by project and study id", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    expect(store.study("p-test-project", "s-test")?.title).toBe("Test Study");
    expect(store.study("p-test-project", "nope")).toBeNull();
  });

  it("keeps uploads and edits across a page reload (localStorage)", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    await store.upload(await upload());
    store.study("p-test-project", "s-test")!.assays[0].title = "Edited";
    await nextTick();

    freshPinia();
    const reloaded = useIsaProjectStore();
    expect(reloaded.has("p-mine")).toBe(true);
    expect(reloaded.study("p-test-project", "s-test")!.assays[0].title).toBe("Edited");
  });
});

describe("isaProjectStore approval (simulated)", () => {
  afterEach(() => vi.useRealTimers());

  /** "p-mine" with its first assay reading ds-new, which came in its bundle. */
  async function bundledProject() {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    const project = JSON.parse(await upload());
    project.investigations[0].studies[0].assays[0].inputs[0].source = { kind: "existing", datasetId: "ds-new" };
    store.addBundle(project, {
      datasets: [{ id: "ds-new", name: "ds-new", category: "measurements", bundled: { fileCount: 1, bytes: 9 } }],
      workflows: [], tools: [],
    });
    return store;
  }
  const entry = (store: ReturnType<typeof useIsaProjectStore>, id = "p-mine") =>
    store.entries.find(e => e.project.project.id === id)!;

  it("walks the approval's stages, then registers the bundled items for every project", async () => {
    vi.useFakeTimers();
    const store = await bundledProject();
    const done = store.approve("p-mine");
    expect(entry(store).approval).toEqual({ state: "approving", stage: "Creating the SEEK project" });
    await vi.advanceTimersByTimeAsync(APPROVE_STEP);
    expect(entry(store).approval).toEqual({ state: "approving", stage: "Registering ds-new" });
    await vi.runAllTimersAsync();
    await done;
    expect(entry(store).approval).toEqual({ state: "approved" });
    expect(entry(store).bundled).toBeUndefined();
    expect(store.registered.datasets).toEqual([{ id: "ds-new", name: "ds-new", category: "measurements" }]);
    expect((await store.platformCatalogue()).datasets.map(d => d.id)).toContain("ds-new");
  });

  it("lets a later JSON upload use a registered item", async () => {
    vi.useFakeTimers();
    const store = await bundledProject();
    const done = store.approve("p-mine");
    await vi.runAllTimersAsync();
    await done;
    const later = { ...entry(store).project, project: { id: "p-later", title: "Later plan" } };
    expect(await store.upload(JSON.stringify(later))).toEqual({ ok: true, projectId: "p-later" });
  });

  it("approves only uploads, not the examples", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    await store.approve("p-test-project");
    expect(entry(store, "p-test-project").approval).toBeUndefined();
  });

  it("drops an approval that a page reload interrupted, so it can be approved again", async () => {
    const store = await bundledProject();
    entry(store).approval = { state: "approving", stage: "Creating the SEEK project" };
    await nextTick();
    freshPinia();
    const reloaded = useIsaProjectStore();
    await reloaded.ensureExamples();
    expect(entry(reloaded).approval).toBeUndefined();
    expect(entry(reloaded).bundled?.datasets).toHaveLength(1);
  });
});


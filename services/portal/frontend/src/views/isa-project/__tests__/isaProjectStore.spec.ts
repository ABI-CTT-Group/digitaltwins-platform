import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";
import { createApp, nextTick } from "vue";
import { useIsaProjectStore } from "../isaProjectStore";
import { fixtureSource } from "../adapter/isaProjectSource";
import { readBundle } from "../adapter/isaBundle";
import { APPROVE_STEP } from "../isaProjectStore";

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

const NOTHING = () => ({ datasets: [], workflows: [], tools: [] });
const RESEARCH = { id: "isa-radiology-research", name: "Radiology research" };
/** Adds "p-mine" as an upload with nothing bundled. */
const addMine = async (store: ReturnType<typeof useIsaProjectStore>) => store.addBundle(JSON.parse(await upload()), NOTHING());

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
      ["p-breast", "example"],
    ]);
  });

  it("drops examples that no longer ship, such as the retired Test Project, but keeps uploads", async () => {
    const store = useIsaProjectStore();
    const old = JSON.parse(await upload());
    store.entries = [
      { project: { ...old, project: { id: "p-test-project", title: "Test Project (example)" } }, source: "example", exampleId: "example-test-project" },
      { project: old, source: "upload" },
    ];
    await store.ensureExamples();
    expect(store.entries.map(e => [e.project.project.id, e.source])).toEqual([
      ["p-mine", "upload"], ["p-breast", "example"],
    ]);
  });

  it("replaces an example stored from an older release of it, but keeps uploads and current examples", async () => {
    const store = useIsaProjectStore();
    const old = JSON.parse(await upload());
    store.entries = [
      { project: { ...old, project: { id: "p-breast", title: "Breast" } }, source: "example", exampleId: "example-breast-pilot" },
      { project: old, source: "upload" },
    ];
    await store.ensureExamples();
    expect(store.entries.map(e => [e.project.project.id, e.source])).toEqual([["p-mine", "upload"], ["p-breast", "example"]]);
    expect(store.study("p-breast", "s-image-pipeline-test")?.title).toBe("Image pipeline test");

    store.study("p-breast", "s-breast-pilot")!.assays[0].title = "Edited";
    await store.ensureExamples();
    expect(store.study("p-breast", "s-breast-pilot")!.assays[0].title).toBe("Edited");
  });

  it("files an upload in the programme chosen for it, and moves a replaced one to the new choice", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    const project = JSON.parse(await upload());
    store.addBundle(project, NOTHING(), RESEARCH);
    expect(store.entries.find(e => e.project.project.id === "p-mine")!.programme).toEqual(RESEARCH);
    expect(store.entries.find(e => e.project.project.id === "p-mine")!.bundled).toBeUndefined(); // a lone JSON brings nothing
    const other = { id: "isa-cardiac", name: "Cardiac" };
    store.addBundle(project, NOTHING(), other);
    expect(store.entries.filter(e => e.project.project.id === "p-mine").map(e => e.programme)).toEqual([other]);
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

  it("removes a project and resets an edited example", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    await addMine(store);
    store.remove("p-mine");
    expect(store.has("p-mine")).toBe(false);

    store.study("p-breast", "s-breast-pilot")!.assays[0].title = "Edited";
    await store.resetExample("p-breast");
    expect(store.study("p-breast", "s-breast-pilot")!.assays[0].title).toBe("1. Cohort selection");
  });

  it("finds a study by project and study id", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    expect(store.study("p-breast", "s-breast-pilot")?.title).toBe("Te Whatu Ora Breast Pilot");
    expect(store.study("p-breast", "nope")).toBeNull();
  });

  it("keeps uploads and edits across a page reload (localStorage)", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    await addMine(store);
    store.study("p-breast", "s-breast-pilot")!.assays[0].title = "Edited";
    await nextTick();

    freshPinia();
    const reloaded = useIsaProjectStore();
    expect(reloaded.has("p-mine")).toBe(true);
    expect(reloaded.study("p-breast", "s-breast-pilot")!.assays[0].title).toBe("Edited");
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
    const later = JSON.stringify({ ...entry(store).project, project: { id: "p-later", title: "Later plan" } });
    const r = await readBundle([{ path: "later.json", size: later.length, text: async () => later }], await store.platformCatalogue());
    expect([r.errors, r.project?.project.id]).toEqual([[], "p-later"]);
  });

  it("approves only uploads, not the examples", async () => {
    const store = useIsaProjectStore();
    await store.ensureExamples();
    await store.approve("p-breast");
    expect(entry(store, "p-breast").approval).toBeUndefined();
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


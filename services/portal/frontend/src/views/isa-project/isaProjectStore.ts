// The ISA projects the prototype knows about: the bundled examples plus any the user uploaded.
// Kept in this browser's localStorage only; nothing is sent to a server.
import { defineStore } from "pinia";
import type { Catalogue, IsaProject, Study } from "./model/types";
import { EXAMPLE_RELEASE, fixtureSource } from "./adapter/isaProjectSource";
import { withBundled } from "./adapter/isaBundle";
import type { IsaProjectEntry, Programme } from "./sandbox";

let seeding: Promise<void> | null = null;
/** Projects whose simulated approval is running in this page. */
const approving = new Set<string>();

/** How long each simulated approval stage takes, in ms. */
export const APPROVE_STEP = 700;
const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
/** A bundled item once it is registered: an ordinary platform item. */
const registeredCopy = <T extends { bundled?: unknown }>(item: T): T => {
  const copy = { ...item };
  delete copy.bundled;
  return copy;
};
const exampleEntry = async (id: string): Promise<IsaProjectEntry> =>
  ({ project: await fixtureSource.loadExample(id), source: "example", exampleId: id, exampleRelease: EXAMPLE_RELEASE });
const addMissing = <T extends { id: string; bundled?: unknown }>(to: T[], items: T[]) =>
  items.forEach(i => { if (!to.some(x => x.id === i.id)) to.push(registeredCopy(i)); });

export const useIsaProjectStore = defineStore("isaProjects", {
  state: () => ({
    entries: [] as IsaProjectEntry[],
    /** Items registered by approvals in this browser; every project can use them. */
    registered: { datasets: [], workflows: [], tools: [] } as Catalogue,
  }),
  getters: {
    has: state => (projectId: string) => state.entries.some(e => e.project.project.id === projectId),
    study: state => (projectId: string, studyId: string): Study | null =>
      state.entries.find(e => e.project.project.id === projectId)?.project.investigations
        .flatMap(i => i.studies).find(s => s.id === studyId) ?? null,
  },
  actions: {
    /** Add any bundled example that isn't in the store yet, and drop stored examples that no
     *  longer ship or come from an older release of their fixture (uploads are kept). Safe to call
     *  repeatedly. */
    ensureExamples(): Promise<void> {
      seeding ??= (async () => {
        // An approval a page reload interrupted never finished: the project can be approved again.
        for (const e of this.entries) {
          if (e.approval?.state === "approving" && !approving.has(e.project.project.id)) delete e.approval;
        }
        const shipped = await fixtureSource.listExamples();
        const ids = new Set(shipped.map(x => x.id));
        this.entries = this.entries.filter(e => e.source !== "example" ||
          (ids.has(e.exampleId ?? "") && e.exampleRelease === EXAMPLE_RELEASE));
        for (const { id } of shipped) {
          if (!this.entries.some(e => e.exampleId === id)) this.entries.push(await exampleEntry(id));
        }
      })().finally(() => { seeding = null; });
      return seeding;
    },

    /** Add an upload (already checked: a lone JSON or a bundle), with any new items its bundle
     *  brought, filed in the programme chosen for it. A project with the same id is replaced in place. */
    addBundle(project: IsaProject, bundled: Catalogue, programme?: Programme) {
      const brings = bundled.datasets.length + bundled.workflows.length + bundled.tools.length > 0;
      this.put({ project, source: "upload", ...(brings ? { bundled } : {}), ...(programme ? { programme } : {}) });
    },

    /** Add an entry; one with the same project id is replaced in place. */
    put(entry: IsaProjectEntry) {
      const at = this.entries.findIndex(e => e.project.project.id === entry.project.project.id);
      if (at >= 0) this.entries.splice(at, 1, entry);
      else this.entries.push(entry);
    },

    /** The platform catalogue plus the items registered in this browser. */
    async platformCatalogue(): Promise<Catalogue> {
      return withBundled(await fixtureSource.catalogue(), this.registered);
    },

    /** Approve an upload (simulated): create its SEEK project, then register each bundled item so
     *  any project can use it. Runs here, not in the dialog, so closing the dialog doesn't stop it. */
    async approve(projectId: string) {
      const entry = this.entries.find(e => e.project.project.id === projectId);
      if (!entry || entry.source !== "upload" || entry.approval) return;
      approving.add(projectId);
      try {
        const items = [...(entry.bundled?.datasets ?? []), ...(entry.bundled?.workflows ?? []), ...(entry.bundled?.tools ?? [])];
        for (const stage of ["Creating the SEEK project", ...items.map(i => `Registering ${i.name}`)]) {
          entry.approval = { state: "approving", stage };
          await wait(APPROVE_STEP);
        }
        if (!this.entries.includes(entry)) return; // removed or replaced meanwhile
        addMissing(this.registered.datasets, entry.bundled?.datasets ?? []);
        addMissing(this.registered.workflows, entry.bundled?.workflows ?? []);
        addMissing(this.registered.tools, entry.bundled?.tools ?? []);
        delete entry.bundled;
        entry.approval = { state: "approved" };
      } finally {
        approving.delete(projectId);
      }
    },

    remove(projectId: string) {
      this.entries = this.entries.filter(e => e.project.project.id !== projectId);
    },

    /** Put an example back as it ships, discarding edits. */
    async resetExample(projectId: string) {
      const at = this.entries.findIndex(e => e.project.project.id === projectId);
      const exampleId = this.entries[at]?.exampleId;
      if (at < 0 || !exampleId) return;
      this.entries.splice(at, 1, await exampleEntry(exampleId));
    },
  },
  persist: true,
});

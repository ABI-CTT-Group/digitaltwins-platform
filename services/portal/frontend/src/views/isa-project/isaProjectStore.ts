// The ISA projects the prototype knows about: the bundled examples plus any the user uploaded.
// Kept in this browser's localStorage only; nothing is sent to a server.
import { defineStore } from "pinia";
import type { Study } from "./model/types";
import { fixtureSource, IsaProjectUploadError } from "./adapter/isaProjectSource";
import type { IsaProjectEntry } from "./sandbox";

let seeding: Promise<void> | null = null;

export const useIsaProjectStore = defineStore("isaProjects", {
  state: () => ({ entries: [] as IsaProjectEntry[] }),
  getters: {
    has: state => (projectId: string) => state.entries.some(e => e.project.project.id === projectId),
    study: state => (projectId: string, studyId: string): Study | null =>
      state.entries.find(e => e.project.project.id === projectId)?.project.investigations
        .flatMap(i => i.studies).find(s => s.id === studyId) ?? null,
  },
  actions: {
    /** Add any bundled example that isn't in the store yet, and drop stored examples that no
     *  longer ship (uploads are kept). Safe to call repeatedly. */
    ensureExamples(): Promise<void> {
      seeding ??= (async () => {
        const shipped = await fixtureSource.listExamples();
        const ids = new Set(shipped.map(x => x.id));
        this.entries = this.entries.filter(e => e.source !== "example" || ids.has(e.exampleId ?? ""));
        for (const { id } of shipped) {
          if (!this.entries.some(e => e.exampleId === id)) {
            this.entries.push({ project: await fixtureSource.loadExample(id), source: "example", exampleId: id });
          }
        }
      })().finally(() => { seeding = null; });
      return seeding;
    },

    /** Add an uploaded draft-schema JSON; a project with the same id is replaced in place. */
    async upload(text: string): Promise<{ ok: true; projectId: string } | { ok: false; errors: string[] }> {
      try {
        const project = await fixtureSource.parseUpload(text);
        const entry: IsaProjectEntry = { project, source: "upload" };
        const at = this.entries.findIndex(e => e.project.project.id === project.project.id);
        if (at >= 0) this.entries.splice(at, 1, entry);
        else this.entries.push(entry);
        return { ok: true, projectId: project.project.id };
      } catch (e) {
        return { ok: false, errors: e instanceof IsaProjectUploadError ? e.errors : [String(e)] };
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
      this.entries.splice(at, 1, { project: await fixtureSource.loadExample(exampleId), source: "example", exampleId });
    },
  },
  persist: true,
});

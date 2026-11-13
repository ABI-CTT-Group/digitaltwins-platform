<template>
  <HubShell
    title="ISA projects"
    subtitle="Upload an ISA project, then open it in the study dashboard to configure all of its assays together."
    accent="#f0b97f"
  >
    <p class="note">
      <v-icon icon="mdi-flask-empty-outline" size="16" />
      Prototype: ISA projects are kept in this browser only. Download one as JSON to keep or share it.
    </p>

    <div class="toolbar">
      <div class="upload">
        <button type="button" class="aurora-btn aurora-btn--solid" @click="fileInput?.click()">
          <v-icon icon="mdi-upload-outline" size="18" /> Upload ISA project (JSON)
        </button>
        <span class="upload__note">Uses datasets and workflows already on the platform.</span>
      </div>
      <div class="upload">
        <button type="button" class="aurora-btn aurora-btn--ghost" data-test="upload-bundle" @click="bundleOpen = true">
          <v-icon icon="mdi-folder-upload-outline" size="18" /> Upload ISA project with datasets
        </button>
        <span class="upload__note">One folder or .zip: the JSON plus the datasets it needs that aren't on the platform yet.</span>
      </div>
      <input ref="fileInput" type="file" accept=".json,application/json" hidden @change="onFile" />
    </div>
    <BundleUploadDialog v-model="bundleOpen" @add="onBundle" />
    <IsaApproveDialog v-model="approveOpen" :project-id="approveId" />

    <div v-if="errors.length" class="errors" role="alert" data-test="upload-errors">
      <p class="errors__lead">{{ errorFile }} can't be loaded as an ISA project:</p>
      <ul><li v-for="e in errors" :key="e">{{ e }}</li></ul>
    </div>

    <ul class="list">
      <li v-for="e in store.entries" :key="e.project.project.id" class="row" data-test="isa-row">
        <div class="row__body">
          <span class="row__title">{{ e.project.project.title }}</span>
          <span class="row__meta">
            <span class="row__source" :class="`row__source--${e.source}`">{{ e.source === "example" ? "Example" : "Uploaded" }}</span>
            {{ summary(e.project) }}{{ e.bundled ? `, ${newItems(e.bundled)}` : "" }}
          </span>
          <span v-if="e.source === 'upload'" class="row__approval" :class="`row__approval--${e.approval?.state ?? 'draft'}`" data-test="approval">
            {{ approvalText(e) }}
          </span>
        </div>
        <div class="row__chains">
          <StudyChain v-for="s in e.project.investigations.flatMap(i => i.studies)" :key="s.id" :study="s" />
        </div>
        <div class="row__actions">
          <button v-if="e.source === 'upload' && !e.approval" type="button" class="aurora-btn aurora-btn--solid" data-test="approve" @click="askApprove(e.project.project.id)">
            Approve
          </button>
          <button type="button" class="aurora-btn aurora-btn--solid" data-test="open" @click="open(e.project.project.id)">
            Open in study dashboard
          </button>
          <button type="button" class="aurora-btn aurora-btn--ghost" @click="download(e.project)">Download JSON</button>
          <button type="button" class="aurora-btn aurora-btn--ghost" data-test="download-bundle" title="The JSON plus an SDS skeleton of each dataset and workflow it uses" @click="downloadBundle(e)">
            Download bundle
          </button>
          <button v-if="e.source === 'upload'" type="button" class="aurora-btn aurora-btn--ghost" data-test="remove" @click="askRemove(e.project)">
            Remove
          </button>
          <button v-else type="button" class="aurora-btn aurora-btn--ghost" data-test="reset" @click="askReset(e.project)">
            Reset
          </button>
        </div>
      </li>
    </ul>

    <ConfirmDialog v-if="confirm.request.value" v-model="confirm.open.value" v-bind="confirm.request.value" />
  </HubShell>
</template>

<script setup lang="ts">
// The catalogue's ISA project hub (prototype): upload draft-schema JSON files and list them. Each
// one appears in the study dashboard under the "Study design sandbox" programme.
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import HubShell from "@/views/upload-dataset/components/HubShell.vue";
import ConfirmDialog from "@/views/upload-dataset/components/ConfirmDialog.vue";
import StudyChain from "./components/StudyChain.vue";
import BundleUploadDialog from "./components/BundleUploadDialog.vue";
import IsaApproveDialog from "./components/IsaApproveDialog.vue";
import { withBundled } from "./adapter/isaBundle";
import { bundleZip, saveBlob } from "./adapter/isaBundleWriter";
import { useConfirm } from "@/views/upload-dataset/components/useConfirm";
import { useIsaProjectStore } from "./isaProjectStore";
import { SANDBOX_ID, type IsaProjectEntry } from "./sandbox";
import type { Catalogue, IsaProject } from "./model/types";

const store = useIsaProjectStore();
const router = useRouter();
const confirm = useConfirm();
const fileInput = ref<HTMLInputElement | null>(null);
const errors = ref<string[]>([]);
const errorFile = ref("");
const bundleOpen = ref(false);
const approveOpen = ref(false);
const approveId = ref<string | null>(null);

onMounted(() => store.ensureExamples());

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function summary(p: IsaProject) {
  const studies = p.investigations.flatMap(i => i.studies);
  return [
    plural(p.investigations.length, "investigation"),
    plural(studies.length, "study", "studies"),
    plural(studies.flatMap(s => s.assays).length, "assay"),
  ].join(", ");
}

/** "with 2 bundled datasets, 1 bundled tool": what a bundle brought that isn't on the platform. */
function newItems(bundled: Catalogue) {
  const parts = [
    [bundled.datasets.length, "bundled dataset"], [bundled.workflows.length, "bundled workflow"], [bundled.tools.length, "bundled tool"],
  ] as const;
  return `with ${parts.filter(([n]) => n).map(([n, one]) => plural(n, one)).join(", ") || "nothing bundled"}`;
}

/** Where an upload stands with the (simulated) platform, as the other hubs' cards say it. */
function approvalText(e: IsaProjectEntry) {
  if (e.approval?.state === "approving") return `Approving… ${e.approval.stage}`;
  if (e.approval?.state === "approved") return "In the platform";
  const n = e.bundled ? e.bundled.datasets.length + e.bundled.workflows.length + e.bundled.tools.length : 0;
  return "Not in the platform yet. Approve it to create its SEEK project" +
    (n ? ` and register its ${plural(n, "bundled item")}.` : ".");
}

function askApprove(projectId: string) {
  approveId.value = projectId;
  approveOpen.value = true;
}

function open(projectId: string) {
  router.push({ name: "StudyDashboard", query: { trail: `${SANDBOX_ID},${SANDBOX_ID}:${projectId}` } });
}

async function load(text: string, name: string) {
  const r = await store.upload(text);
  errors.value = r.ok ? [] : r.errors;
  errorFile.value = name;
}

async function onFile(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  const text = await file.text();
  let id: unknown;
  try { id = JSON.parse(text)?.project?.id; } catch { /* store.upload reports bad JSON */ }
  const existing = store.entries.find(x => x.project.project.id === id);
  if (!existing) return load(text, file.name);
  confirm.ask({
    title: `Replace ${existing.project.project.title}?`,
    text: `${file.name} has the same project id. Replacing it discards the current version and any changes made in the study dashboard.`,
    confirmLabel: "Replace",
    action: () => load(text, file.name),
  });
}

function onBundle({ project, bundled }: { project: IsaProject; bundled: Catalogue }) {
  errors.value = [];
  const existing = store.entries.find(x => x.project.project.id === project.project.id);
  if (!existing) return store.addBundle(project, bundled);
  confirm.ask({
    title: `Replace ${existing.project.project.title}?`,
    text: "The bundle has the same project id. Replacing it discards the current version and any changes made in the study dashboard.",
    confirmLabel: "Replace",
    action: async () => store.addBundle(project, bundled),
  });
}

function download(p: IsaProject) {
  saveBlob(new Blob([JSON.stringify(p, null, 2)], { type: "application/json" }), `${p.project.id}.isa-project.json`);
}

/** The project's JSON plus an SDS skeleton of each dataset and workflow it uses (no files are kept). */
async function downloadBundle(e: IsaProjectEntry) {
  const catalogue = withBundled(await store.platformCatalogue(), e.bundled);
  saveBlob(await bundleZip(e.project, catalogue), `${e.project.project.id}.isa-bundle.zip`);
}

const askRemove = (p: IsaProject) => confirm.ask({
  title: `Remove ${p.project.title}?`,
  text: "It disappears from this list and from the study dashboard. Download it first if you want to keep it." +
    (store.entries.find(e => e.project === p)?.approval?.state === "approved"
      ? " Its registered datasets, workflows and tools stay." : ""),
  confirmLabel: "Remove",
  action: async () => store.remove(p.project.id),
});

const askReset = (p: IsaProject) => confirm.ask({
  title: `Reset ${p.project.title}?`,
  text: "This puts the example back as it ships, discarding changes made in the study dashboard.",
  confirmLabel: "Reset",
  action: () => store.resetExample(p.project.id),
});
</script>

<style scoped>
.note { display: flex; align-items: center; gap: 6px; margin: 0 0 18px; font-size: 0.86rem; color: var(--tone-needs); }
.toolbar { display: flex; flex-wrap: wrap; gap: 12px 28px; margin-bottom: 20px; }
.toolbar .aurora-btn { display: inline-flex; align-items: center; gap: 8px; }
.upload { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; max-width: 34ch; }
.upload__note { font-size: 0.82rem; line-height: 1.4; color: var(--text-dim); }

.errors {
  margin-bottom: 20px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--tone-failed) 45%, transparent);
  color: var(--text);
}
.errors__lead { margin: 0 0 4px; font-weight: 600; color: var(--tone-failed); }
.errors ul { margin: 0; padding-left: 1.2em; color: var(--text-dim); }

.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--accent);
  background: var(--surface);
}
.row__body { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.row__title { font-size: 1.05rem; font-weight: 600; color: #fff; }
.row__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 0.85rem; color: var(--text-dim); }
.row__source { padding: 1px 8px; border-radius: 999px; border: 1px solid var(--line); font-size: 0.76rem; }
.row__source--upload { border-color: color-mix(in srgb, var(--accent) 55%, transparent); color: var(--accent); }
/* Quiet when fine, loud when not, as on the other hubs' cards. */
.row__approval { font-size: 0.85rem; color: var(--text-dim); }
.row__approval--draft { color: var(--tone-needs); }
.row__approval--approving { color: var(--text); }
.row__actions { display: flex; flex-wrap: wrap; gap: 8px; }
/* The chains take a line of their own under the title and actions. */
.row__chains { order: 3; flex-basis: 100%; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
</style>

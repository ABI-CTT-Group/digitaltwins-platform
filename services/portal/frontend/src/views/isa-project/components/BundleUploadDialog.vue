<template>
  <v-dialog v-model="open" max-width="680" scrollable>
    <div class="bundle" data-test="bundle-dialog" role="dialog" aria-labelledby="bundle-title">
      <h2 id="bundle-title" class="bundle__title">Upload ISA project with datasets</h2>

      <template v-if="!read">
        <p class="bundle__text">
          For a design whose data or workflows aren't on the platform yet. Pick one folder or .zip that holds
          the ISA project JSON and an SDS folder for each dataset, workflow or tool it uses that isn't on the platform
          yet, named by the id the design uses.
        </p>
        <pre class="bundle__tree" aria-label="Bundle layout">my-project/
├── isa-project.json
└── datasets/
    ├── &lt;dataset id&gt;/       dataset_description.xlsx, and its files under primary/
    ├── &lt;workflow id&gt;/      dataset_description.xlsx, primary/workflow_*.cwl and its tool_*.cwl
    └── &lt;tool id&gt;/          dataset_description.xlsx, primary/tool_*.cwl</pre>
        <p class="bundle__hint">Each folder is matched to a <code>datasets/&lt;id&gt;/</code> the JSON names. Only file names and sizes are kept in this browser, not the files.</p>
        <p class="bundle__hint">
          <button type="button" class="bundle__link" data-test="bundle-example" @click="downloadExample">Download an example bundle</button>
          to try it: the Test Project with one bundled dataset, workflow and tool, with placeholder files.
        </p>
        <LocalFolderDropzone :key="attempt" @source-selected="onSource" />
        <p v-if="reading" class="bundle__hint" aria-live="polite">Reading the bundle…</p>
      </template>

      <div v-else data-test="bundle-review" class="review">
        <p class="review__project">
          <span class="review__name">{{ read.project?.project.title ?? source }}</span>
          <span v-if="read.project" class="review__counts">{{ counts }}</span>
        </p>

        <div v-if="read.errors.length" class="notes notes--error" role="alert" data-test="bundle-errors">
          <p class="notes__lead">{{ source }} can't be added yet:</p>
          <ul><li v-for="e in read.errors" :key="e">{{ e }}</li></ul>
        </div>

        <template v-if="manifest">
          <h3 class="review__heading">Bundled items</h3>
          <p v-if="!manifest.rows.length" class="bundle__hint">
            Nothing: everything this design uses is already on the platform. The JSON upload would do.
          </p>
          <ul class="items">
            <li v-for="r in manifest.rows" :key="`${r.kind}:${r.id}`" class="item" :class="`item--${r.kind}`" data-test="bundle-item">
              <span class="item__name">{{ r.name }}</span>
              <span class="item__kind">{{ KIND_LABEL[r.kind] }}</span>
              <span class="item__meta">{{ r.meta }}</span>
              <span class="item__used">{{ r.usedBy.length ? `Used by ${r.usedBy.join(", ")}` : "Not used" }}</span>
            </li>
          </ul>
          <p class="bundle__hint" data-test="bundle-on-platform">Already on the platform: {{ onPlatform }}.</p>
        </template>

        <div v-if="read.warnings.length" class="notes notes--warn" data-test="bundle-warnings">
          <ul><li v-for="w in read.warnings" :key="w">{{ w }}</li></ul>
        </div>
      </div>

      <div class="bundle__actions">
        <button type="button" class="aurora-btn aurora-btn--ghost" @click="open = false">Cancel</button>
        <template v-if="read">
          <button type="button" class="aurora-btn aurora-btn--ghost" data-test="bundle-again" @click="reset">Choose another bundle</button>
          <button type="button" class="aurora-btn aurora-btn--solid" data-test="bundle-add" :disabled="!read.project" @click="add">
            Add project
          </button>
        </template>
      </div>
    </div>
  </v-dialog>
</template>

<script setup lang="ts">
// Upload an ISA project together with the datasets, workflows and tools it uses that aren't on the
// platform yet (prototype). Reads the bundle in the browser and shows what it adds before adding.
import { computed, ref, watch } from "vue";
import type { LocalSource } from "@/bootstrap/upload_source";
import LocalFolderDropzone from "@/views/upload-dataset/components/LocalFolderDropzone.vue";
import { bundleFiles, bundleManifest, readBundle, withBundled, type BundleRead } from "../adapter/isaBundle";
import { bundleZip, demoBundle, saveBlob } from "../adapter/isaBundleWriter";
import { useIsaProjectStore } from "../isaProjectStore";
import type { Catalogue, IsaProject } from "../model/types";

const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ (e: "add", bundle: { project: IsaProject; bundled: Catalogue }): void }>();

const KIND_LABEL = { dataset: "Dataset", workflow: "Workflow", tool: "Tool" } as const;

const store = useIsaProjectStore();
const read = ref<BundleRead | null>(null);
const catalogue = ref<Catalogue | null>(null);
const source = ref("");
const reading = ref(false);
/** Remounts the dropzone so a new pick starts clean. */
const attempt = ref(0);

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

const manifest = computed(() => (read.value?.project && catalogue.value
  ? bundleManifest(read.value.project, read.value.bundled, catalogue.value)
  : null));

const counts = computed(() => {
  const p = read.value?.project;
  if (!p) return "";
  const studies = p.investigations.flatMap(i => i.studies);
  return [plural(p.investigations.length, "investigation"), plural(studies.length, "study", "studies"),
    plural(studies.flatMap(s => s.assays).length, "assay")].join(", ");
});

const onPlatform = computed(() => {
  const n = manifest.value?.onPlatform;
  if (!n) return "";
  const parts = [plural(n.datasets, "dataset"), plural(n.workflows, "workflow"), plural(n.tools, "tool")];
  return parts.filter(s => !s.startsWith("0 ")).join(", ") || "nothing";
});

async function onSource(s: LocalSource) {
  reading.value = true;
  source.value = s.rootName;
  try {
    catalogue.value = await store.platformCatalogue();
    read.value = await readBundle(await bundleFiles(s), catalogue.value);
  } catch (e) {
    read.value = { project: null, bundled: { datasets: [], workflows: [], tools: [] }, warnings: [],
      errors: [`The bundle can't be read: ${e instanceof Error ? e.message : String(e)}`] };
  } finally {
    reading.value = false;
  }
}

async function downloadExample() {
  const platform = await store.platformCatalogue();
  const { project, bundled } = demoBundle(platform);
  saveBlob(await bundleZip(project, withBundled(platform, bundled), { only: "bundled" }), `${project.project.id}.isa-bundle.zip`);
}

function reset() {
  read.value = null;
  attempt.value++;
}

function add() {
  if (!read.value?.project) return;
  emit("add", { project: read.value.project, bundled: read.value.bundled });
  open.value = false;
}

watch(open, isOpen => { if (isOpen) reset(); });
</script>

<style scoped>
.bundle {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 88vh;
  overflow-y: auto;
  padding: 24px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--ink);
  font-family: var(--font-ui);
  color: var(--text);
}
.bundle__title { margin: 0; font-size: 1.2rem; font-weight: 600; }
.bundle__text { margin: 0; line-height: 1.55; color: var(--text-dim); max-width: 64ch; }
.bundle__hint { margin: 0; font-size: 0.86rem; line-height: 1.5; color: var(--text-dim); }
.bundle__tree {
  margin: 0;
  padding: 12px 14px;
  overflow-x: auto;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: var(--surface);
  font-size: 0.8rem;
  line-height: 1.55;
  color: var(--text);
}
.bundle__link {
  padding: 0;
  border: 0;
  background: none;
  color: var(--accent-tools);
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
}
.bundle__link:focus-visible { outline: 2px solid var(--accent-tools); outline-offset: 2px; }
.bundle__actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; margin-top: 6px; }

.review { display: flex; flex-direction: column; gap: 12px; }
.review__project { display: flex; flex-direction: column; gap: 2px; margin: 0; }
.review__name { font-size: 1.05rem; font-weight: 600; }
.review__counts { font-size: 0.86rem; color: var(--text-dim); }
.review__heading { margin: 4px 0 0; font-size: 0.95rem; font-weight: 600; }

/* One row per new item; the left bar takes the colour the platform gives that kind of dataset. */
.items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.item {
  --kind: var(--accent-measurements);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2px 12px;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--kind);
  background: color-mix(in srgb, var(--kind) 6%, transparent);
}
.item--workflow { --kind: var(--accent-workflows); }
.item--tool { --kind: var(--accent-tools); }
.item__name { font-weight: 600; overflow-wrap: anywhere; }
.item__kind { justify-self: end; font-size: 0.8rem; color: var(--kind); }
.item__meta, .item__used { grid-column: 1 / -1; font-size: 0.84rem; color: var(--text-dim); }

.notes { padding: 10px 14px; border-radius: 10px; font-size: 0.86rem; }
.notes ul { margin: 0; padding-left: 1.2em; color: var(--text-dim); }
.notes li + li { margin-top: 4px; }
.notes__lead { margin: 0 0 4px; font-weight: 600; color: var(--tone-failed); }
.notes--error { border: 1px solid color-mix(in srgb, var(--tone-failed) 45%, transparent); }
.notes--warn { border: 1px solid color-mix(in srgb, var(--tone-needs) 40%, transparent); }
.notes--warn ul { color: var(--tone-needs); }
</style>

<template>
  <HubShell
    title="ISA projects"
    subtitle="Upload an ISA project, then open it in the study dashboard to configure all of its assays together."
    accent="#f0b97f"
  >

    <div class="upload">
      <button type="button" class="aurora-btn aurora-btn--solid" data-test="upload" @click="bundleOpen = true">
        <v-icon icon="mdi-upload-outline" size="18" /> Upload ISA project
      </button>
      <span class="upload__note">A JSON file, or a folder or .zip with the datasets it needs that aren't on the platform yet.</span>
    </div>
    <BundleUploadDialog v-model="bundleOpen" @add="onBundle" />
    <IsaApproveDialog v-model="approveOpen" :project-id="approveId" />

    <section v-for="g in groups" :key="g.programme.id" class="programme" data-test="isa-programme" :aria-labelledby="`programme-${g.programme.id}`">
      <h2 :id="`programme-${g.programme.id}`" class="programme__head">
        <span class="programme__name" data-test="isa-programme-name">{{ g.programme.name }}</span>
        <span class="programme__count">{{ plural(g.entries.length, "project") }}</span>
      </h2>
      <ul class="list">
        <li v-for="e in g.entries" :key="e.project.project.id" class="row" data-test="isa-row" :data-project="e.project.project.id">
          <div class="row__body">
            <span class="row__title">{{ e.project.project.title }}</span>
            <span class="row__meta">
              {{ summary(e.project) }}{{ e.bundled ? `, ${newItems(e.bundled)}` : "" }}
            </span>
            <span v-if="e.source === 'upload'" class="row__approval" :class="`row__approval--${e.approval?.state ?? 'draft'}`" data-test="approval">
              {{ approvalText(e) }}
            </span>
          </div>
          <div class="row__actions">
            <button v-if="e.source === 'upload' && !e.approval" type="button" class="aurora-btn aurora-btn--solid" data-test="approve" @click="askApprove(e.project.project.id)">
              Approve
            </button>
            <button type="button" class="aurora-btn aurora-btn--solid" data-test="open" @click="open(e, [])">
              Open in study dashboard
            </button>
            <v-menu location="bottom end" :offset="8">
              <template #activator="{ props: act, isActive }">
                <button type="button" class="more" :class="{ 'is-open': isActive }" v-bind="act" aria-label="More actions" data-test="more">
                  <v-icon icon="mdi-dots-horizontal" size="18" />
                </button>
              </template>
              <div class="menu" :data-test="`menu-${e.project.project.id}`">
                <button type="button" class="menu__item" data-test="download-json" @click="download(e.project)">
                  <v-icon icon="mdi-code-json" size="16" class="menu__icon" /><span>Download JSON</span>
                </button>
                <button type="button" class="menu__item" data-test="download-bundle" title="The JSON plus an SDS skeleton of each dataset and workflow it uses" @click="downloadBundle(e)">
                  <v-icon icon="mdi-folder-zip-outline" size="16" class="menu__icon" /><span>Download bundle</span>
                </button>
                <button v-if="e.source === 'upload'" type="button" class="menu__item is-danger" data-test="remove" @click="askRemove(e.project)">
                  <v-icon icon="mdi-delete-outline" size="16" class="menu__icon" /><span>Remove</span>
                </button>
                <button v-else type="button" class="menu__item" data-test="reset" @click="askReset(e.project)">
                  <v-icon icon="mdi-restore" size="16" class="menu__icon" /><span>Reset</span>
                </button>
              </div>
            </v-menu>
          </div>
          <!-- The ISA tree: solid rails mean "contains"; each study's chain keeps the dashed "flows into". -->
          <ul class="tree" :aria-label="`${e.project.project.title}: investigations and studies`">
            <li v-for="inv in e.project.investigations" :key="inv.id" class="tree__node" data-test="isa-investigation">
              <button type="button" class="node node--investigation" data-test="isa-investigation-open" @click="open(e, [inv.id])">
                <span class="node__title">{{ inv.title }}</span>
                <span class="node__level">investigation</span>
              </button>
              <p v-if="!inv.studies.length" class="tree__empty">No studies yet</p>
              <ul v-else class="tree">
                <li v-for="s in inv.studies" :key="s.id" class="tree__node" data-test="isa-study">
                  <button type="button" class="node node--study" data-test="isa-study-open" @click="open(e, [inv.id, s.id])">
                    <span class="node__title">{{ s.title }}</span>
                    <span class="node__level">study, {{ plural(s.assays.length, "assay") }}</span>
                  </button>
                  <StudyChain :study="s" class="tree__chain" />
                </li>
              </ul>
            </li>
          </ul>
        </li>
      </ul>
    </section>

    <ConfirmDialog v-if="confirm.request.value" v-model="confirm.open.value" v-bind="confirm.request.value" />
  </HubShell>
</template>

<script setup lang="ts">
// The catalogue's ISA project hub (prototype): upload ISA projects (a draft-schema JSON, or a bundle
// with it) and list them, grouped by programme. Each one appears in the Study dashboard (prototype)
// under the programme it was filed in; the examples are in "Te Whatu Ora Radiology Reporting".
import { computed, onMounted, ref } from "vue";
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
import { knownProgrammes, programmeOf, type IsaProjectEntry, type Programme } from "./sandbox";
import type { Catalogue, IsaProject } from "./model/types";

const store = useIsaProjectStore();
const router = useRouter();
const confirm = useConfirm();
const bundleOpen = ref(false);
const approveOpen = ref(false);
const approveId = ref<string | null>(null);

onMounted(() => store.ensureExamples());

/** The projects under each programme that has any, the built-in programme first. */
const groups = computed(() => knownProgrammes(store.entries)
  .map(programme => ({ programme, entries: store.entries.filter(e => programmeOf(e).id === programme.id) }))
  .filter(g => g.entries.length));

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

/** Opens the study dashboard at a project, or deeper at one of its investigations or studies. */
function open(e: IsaProjectEntry, below: string[]) {
  const ids = [programmeOf(e).id, e.project.project.id, ...below];
  const trail = ids.map((_, n) => ids.slice(0, n + 1).join(":"));
  router.push({ name: "StudyDashboardPrototype", query: { trail: trail.join(",") } });
}

function onBundle({ project, bundled, programme }: { project: IsaProject; bundled: Catalogue; programme: Programme }) {
  const existing = store.entries.find(x => x.project.project.id === project.project.id);
  if (!existing) return store.addBundle(project, bundled, programme);
  confirm.ask({
    title: `Replace ${existing.project.project.title}?`,
    text: "The upload has the same project id. Replacing it discards the current version and any changes made in the study dashboard.",
    confirmLabel: "Replace",
    action: async () => store.addBundle(project, bundled, programme),
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
.upload { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; max-width: 46ch; margin-bottom: 28px; }
.upload .aurora-btn { display: inline-flex; align-items: center; gap: 8px; }
.upload__note { font-size: 0.82rem; line-height: 1.4; color: var(--text-dim); }

/* A programme: the ISA tree's top level, over its projects' cards. */
.programme + .programme { margin-top: 32px; }
.programme__head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; margin: 0 0 12px; font-weight: 400; }
.programme__name { font-size: 1.05rem; font-weight: 600; color: var(--text); }
.programme__count { font-size: 0.82rem; color: var(--text-faint); }

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
.row__title { font-family: var(--font-title); font-size: 1.35rem; font-weight: 500; line-height: 1.2; color: #fff; }
.row__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 0.85rem; color: var(--text-dim); }
/* Quiet when fine, loud when not, as on the other hubs' cards. */
.row__approval { font-size: 0.85rem; color: var(--text-dim); }
.row__approval--draft { color: var(--tone-needs); }
.row__approval--approving { color: var(--text); }
.row__actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }

/* The More actions menu, in the look of the other hubs' cards (CardUI.vue). */
.more {
  display: inline-grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-dim);
  cursor: pointer;
}
.more:hover, .more.is-open { border-color: color-mix(in srgb, var(--accent) 50%, transparent); color: var(--text); }
.more:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.menu {
  min-width: 210px;
  padding: 6px;
  border-radius: 12px;
  background: rgba(8, 18, 26, 0.98);
  border: 1px solid var(--line);
  box-shadow: 0 18px 40px -16px rgba(0, 0, 0, 0.8);
}
.menu__item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 11px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 0.875rem;
  text-align: left;
  cursor: pointer;
}
.menu__item:hover, .menu__item:focus-visible { background: rgba(255, 255, 255, 0.06); outline: none; }
.menu__icon { color: var(--text-faint); }
.menu__item:hover .menu__icon { color: var(--text); }
.menu__item.is-danger, .menu__item.is-danger .menu__icon { color: var(--tone-failed); }
.menu__item.is-danger:hover { background: color-mix(in srgb, var(--tone-failed) 12%, transparent); }

/* The ISA tree, on a line of its own under the title and actions. Solid rails mean "contains";
   the dashed lines inside each study's chain mean "flows into". */
.row > .tree { order: 3; flex-basis: 100%; min-width: 0; padding-left: 2px; }
.tree { --rail: color-mix(in srgb, var(--text-faint) 55%, transparent); --elbow: 18px; list-style: none; margin: 0; padding: 0; }
.tree .tree { padding-left: 14px; }
.tree__node { position: relative; padding-left: 22px; min-width: 0; }
.tree__node::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; border-left: 1px solid var(--rail); }
.tree__node:last-child::before { bottom: auto; height: var(--elbow); }
.tree__node::after { content: ""; position: absolute; left: 0; top: var(--elbow); width: 16px; border-top: 1px solid var(--rail); }
.tree__empty { margin: 2px 0 6px 22px; font-size: 0.82rem; color: var(--text-faint); }
.tree__chain { padding: 2px 0 16px 8px; }

.node {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px 10px;
  max-width: 100%;
  min-height: 36px;
  padding: 7px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.node:hover { background: rgba(255, 255, 255, 0.04); }
.node:hover .node__title, .node:focus-visible .node__title { color: var(--accent); }
.node:focus-visible { outline: 2px solid var(--accent); outline-offset: 0; }
.node__title { font-size: 0.95rem; }
.node--investigation .node__title { font-weight: 600; }
.node--study .node__title { font-weight: 500; }
.node__level { font-size: 0.8rem; color: var(--text-faint); }
</style>

<template>
  <div class="folder-dropzone-wrapper">
    <div
      class="dropzone"
      :class="{
        'dropzone--active': dragActive,
        'dropzone--error': phase === 'error',
        'dropzone--ready': phase === 'ready',
        'dropzone--busy': isBusy,
      }"
      @dragover.prevent="onDragOver"
      @dragleave.prevent="dragActive = false"
      @drop.prevent="onDrop"
      @click="triggerFolderInput"
    >
      <input
        ref="folderInput"
        type="file"
        multiple
        webkitdirectory
        directory
        style="display: none"
        @change="onFolderInputChange"
      />
      <input
        ref="zipInput"
        type="file"
        accept=".zip,application/zip,application/x-zip-compressed"
        style="display: none"
        @change="onZipInputChange"
      />

      <div v-if="phase === 'idle'" class="dropzone__hint">
        <v-icon size="42" color="#5fd6e8">mdi-folder-upload-outline</v-icon>
        <div class="text-h6 mt-2">Drag a folder or a .zip file here, or click to browse</div>
        <div class="text-caption text-grey-lighten-1 mt-1">
          Large datasets upload in resumable chunks. We auto-skip
          <code>node_modules</code>, <code>.git</code>, <code>dist</code>, <code>build</code>.
          Max total size {{ formatBytes(MAX_TOTAL_BYTES) }}.
        </div>
        <a
          href="#"
          class="text-caption dz-link mt-2 d-inline-block"
          @click.stop.prevent="triggerZipInput"
        >
          Or pick a .zip file
        </a>
      </div>

      <div v-else-if="phase === 'scanning'" class="dropzone__progress">
        <v-progress-circular indeterminate color="#5fd6e8" :size="36" :width="3" />
        <div class="text-subtitle-2 mt-2">Scanning folder…</div>
        <div v-if="scannedCount > 0" class="text-caption text-grey-lighten-1 mt-1">
          {{ scannedCount }} files seen
        </div>
      </div>

      <div v-else-if="phase === 'scanned'" class="dropzone__hint">
        <v-icon size="36" color="#5fd6e8">
          {{ scanKind === 'zip' ? 'mdi-zip-box-outline' : 'mdi-folder-check-outline' }}
        </v-icon>
        <div class="text-subtitle-1 mt-1">
          {{ rootName || (scanKind === 'zip' ? 'Archive selected' : 'Folder selected') }}
          <span v-if="scanKind === 'zip'" class="text-caption text-grey-lighten-1">(.zip)</span>
        </div>
        <div class="text-caption mt-1">
          <template v-if="scanKind === 'folder'">
            {{ keptCount }} files · {{ formatBytes(keptSize) }}
            <span v-if="skippedCount > 0">
              · skipped {{ skippedCount }} ({{ formatBytes(skippedSize) }})
            </span>
          </template>
          <template v-else>{{ formatBytes(keptSize) }}</template>
        </div>
        <div class="text-caption text-grey-lighten-1 mt-1">Click to choose a different source.</div>
      </div>

      <div v-else-if="phase === 'uploading' || phase === 'paused'" class="dropzone__progress">
        <v-progress-linear v-model="progressPercent" striped height="10" color="#5fd6e8" />
        <div class="text-caption mt-2">
          {{ phase === 'paused' ? 'Paused' : 'Uploading' }}…
          {{ formatBytes(sentBytes) }} / {{ formatBytes(totalBytes) }} ·
          {{ sentParts }} / {{ totalParts }} parts · {{ Math.round(progressPercent) }}%
        </div>
        <div class="d-flex justify-center mt-2" @click.stop>
          <v-btn
            v-if="phase === 'uploading'"
            size="small"
            variant="text"
            color="#5fd6e8"
            @click="emit('pause-requested')"
          >
            Pause
          </v-btn>
          <v-btn
            v-else
            size="small"
            variant="text"
            color="#5fd6e8"
            @click="emit('resume-requested')"
          >
            Resume
          </v-btn>
          <v-btn size="small" variant="text" color="error" @click="emit('cancel-requested')">
            Cancel
          </v-btn>
        </div>
      </div>

      <div v-else-if="phase === 'finalizing'" class="dropzone__progress">
        <v-progress-circular indeterminate color="#5fd6e8" :size="36" :width="3" />
        <div class="text-caption mt-2">Finalizing on server…</div>
        <div class="text-caption text-grey-lighten-1 mt-1">
          All parts sent — the server is assembling and validating your dataset.
        </div>
      </div>

      <div v-else-if="phase === 'ready'" class="dropzone__hint">
        <v-icon size="36" color="success">mdi-check-circle-outline</v-icon>
        <div class="text-subtitle-1 mt-1">Source uploaded.</div>
        <div class="text-caption text-grey-lighten-1 mt-1">Click to replace this source.</div>
      </div>

      <div v-else-if="phase === 'error'" class="dropzone__hint">
        <v-icon size="36" color="error">mdi-alert-circle-outline</v-icon>
        <div class="text-subtitle-1 mt-1 text-error">{{ errorMessage }}</div>
        <div class="text-caption text-grey-lighten-1 mt-1">Click to try again.</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { LocalSource } from '@/bootstrap/upload_source';
import {
  captureDataTransfer,
  filterFolderFiles,
  formatBytes,
  isZipFile,
  traverseEntry,
} from '@/composables/useFolderScan';

export type ChunkedDropzonePhase =
  | 'idle'
  | 'scanning'
  | 'scanned'
  | 'uploading'
  | 'paused'
  | 'finalizing'
  | 'ready'
  | 'error';

const props = withDefaults(
  defineProps<{ maxTotalBytes?: number }>(),
  { maxTotalBytes: 20 * 1024 * 1024 * 1024 },
);

const emit = defineEmits<{
  (e: 'source-selected', source: LocalSource): void;
  (e: 'phase-change', phase: ChunkedDropzonePhase): void;
  (e: 'pause-requested'): void;
  (e: 'resume-requested'): void;
  (e: 'cancel-requested'): void;
}>();

const MAX_TOTAL_BYTES = computed(() => props.maxTotalBytes);

const folderInput = ref<HTMLInputElement | null>(null);
const zipInput = ref<HTMLInputElement | null>(null);
const dragActive = ref(false);

const phase = ref<ChunkedDropzonePhase>('idle');
const scanKind = ref<'folder' | 'zip'>('folder');
const rootName = ref('');
const keptCount = ref(0);
const keptSize = ref(0);
const skippedCount = ref(0);
const skippedSize = ref(0);
const scannedCount = ref(0);
const errorMessage = ref('');

// Upload progress, fed by the parent via setProgress().
const progressPercent = ref(0);
const sentBytes = ref(0);
const totalBytes = ref(0);
const sentParts = ref(0);
const totalParts = ref(0);

const isBusy = computed(
  () =>
    phase.value === 'scanning'
    || phase.value === 'uploading'
    || phase.value === 'paused'
    || phase.value === 'finalizing',
);

function setPhase(next: ChunkedDropzonePhase) {
  phase.value = next;
  emit('phase-change', next);
}

async function yieldToPaint(minMs = 120): Promise<void> {
  await new Promise<void>((r) => requestAnimationFrame(() => r()));
  if (minMs > 0) await new Promise((r) => setTimeout(r, minMs));
}

function reset() {
  rootName.value = '';
  keptCount.value = 0;
  keptSize.value = 0;
  skippedCount.value = 0;
  skippedSize.value = 0;
  scannedCount.value = 0;
  progressPercent.value = 0;
  sentBytes.value = 0;
  totalBytes.value = 0;
  sentParts.value = 0;
  totalParts.value = 0;
  errorMessage.value = '';
  if (folderInput.value) folderInput.value.value = '';
  if (zipInput.value) zipInput.value.value = '';
}

function triggerFolderInput() {
  if (isBusy.value) return;
  folderInput.value?.click();
}
function triggerZipInput() {
  if (isBusy.value) return;
  zipInput.value?.click();
}
function onDragOver() {
  if (isBusy.value) return;
  dragActive.value = true;
}

async function onDrop(ev: DragEvent) {
  dragActive.value = false;
  if (!ev.dataTransfer) return;
  if (isBusy.value) return;

  const { flatFiles, captured } = captureDataTransfer(ev.dataTransfer);

  if (flatFiles.length === 1 && isZipFile(flatFiles[0])) {
    handleZipFile(flatFiles[0]);
    return;
  }

  reset();
  scanKind.value = 'folder';
  setPhase('scanning');
  await yieldToPaint();

  try {
    const out: File[] = [];
    for (const c of captured) {
      if (c.entry) {
        await traverseEntry(c.entry, out, '', (count) => { scannedCount.value = count; });
      } else if (c.file) {
        out.push(c.file);
      }
    }
    finalizeFolderScan(out);
  } catch (err) {
    console.error('Folder scan failed:', err);
    errorMessage.value = 'Failed to read the dropped folder. Try clicking to browse instead.';
    setPhase('error');
  }
}

async function onFolderInputChange(ev: Event) {
  const target = ev.target as HTMLInputElement;
  if (!target.files) return;
  const files = Array.from(target.files);
  reset();
  scanKind.value = 'folder';
  scannedCount.value = files.length;
  setPhase('scanning');
  await yieldToPaint();
  finalizeFolderScan(files);
}

function onZipInputChange(ev: Event) {
  const target = ev.target as HTMLInputElement;
  const f = target.files?.[0];
  if (!f) return;
  handleZipFile(f);
}

function finalizeFolderScan(files: File[]) {
  if (files.length === 0) {
    errorMessage.value = 'No files found in that selection.';
    setPhase('error');
    return;
  }

  const { kept, keptSize: keptS, skippedCount: skippedC, skippedSize: skippedS, rootName: root } =
    filterFolderFiles(files);

  if (kept.length === 0) {
    errorMessage.value = 'No files left after filtering. Did you drop an empty or fully-skipped folder?';
    setPhase('error');
    return;
  }
  if (keptS > MAX_TOTAL_BYTES.value) {
    errorMessage.value = `Folder is ${formatBytes(keptS)} after filtering — exceeds the ${formatBytes(MAX_TOTAL_BYTES.value)} upload limit.`;
    setPhase('error');
    return;
  }

  rootName.value = root;
  keptCount.value = kept.length;
  keptSize.value = keptS;
  skippedCount.value = skippedC;
  skippedSize.value = skippedS;

  setPhase('scanned');
  emit('source-selected', {
    kind: 'folder',
    files: kept,
    rootName: root,
    fileCount: kept.length,
    totalSize: keptS,
  });
}

// Zip mode deliberately does NOT load the archive (JSZip would read the whole
// blob into memory — exactly what chunking avoids on large files). We stream
// the blob as-is; the root name is the filename minus .zip.
function handleZipFile(file: File) {
  reset();
  scanKind.value = 'zip';

  if (file.size > MAX_TOTAL_BYTES.value) {
    errorMessage.value = `Archive is ${formatBytes(file.size)} — exceeds the ${formatBytes(MAX_TOTAL_BYTES.value)} upload limit.`;
    setPhase('error');
    return;
  }

  rootName.value = file.name.replace(/\.zip$/i, '');
  keptCount.value = 0;
  keptSize.value = file.size;
  skippedCount.value = 0;
  skippedSize.value = 0;

  setPhase('scanned');
  emit('source-selected', {
    kind: 'zip',
    blob: file,
    rootName: rootName.value,
    fileCount: 0,
    totalSize: file.size,
  });
}

// ---- API exposed to the parent (which drives the ChunkedUploader) ----------
function setProgress(
  p:
    | { phase: 'uploading' }
    | { phase: 'upload'; sentBytes: number; totalBytes: number; percent: number; sentParts: number; totalParts: number }
    | { phase: 'paused' }
    | { phase: 'finalizing' }
    | { phase: 'ready' }
    | { phase: 'error'; message: string }
    | { phase: 'reset' },
) {
  // Phase is driven solely by 'uploading'/'paused'/'finalizing' (from the
  // uploader's onPhase). 'upload' only updates the numbers, so straggler
  // progress after a pause can never flip the UI back out of 'paused'.
  if (p.phase === 'uploading') {
    setPhase('uploading');
    return;
  }
  if (p.phase === 'upload') {
    progressPercent.value = p.percent;
    sentBytes.value = p.sentBytes;
    totalBytes.value = p.totalBytes;
    sentParts.value = p.sentParts;
    totalParts.value = p.totalParts;
    return;
  }
  if (p.phase === 'paused') {
    setPhase('paused');
    return;
  }
  if (p.phase === 'finalizing') {
    setPhase('finalizing');
    return;
  }
  if (p.phase === 'ready') {
    setPhase('ready');
    return;
  }
  if (p.phase === 'error') {
    errorMessage.value = p.message;
    setPhase('error');
    return;
  }
  if (p.phase === 'reset') {
    reset();
    setPhase('idle');
  }
}

defineExpose({ setProgress });
</script>

<style scoped>
.folder-dropzone-wrapper {
  width: 100%;
}
.dropzone {
  border: 2px dashed rgba(255, 255, 255, 0.25);
  border-radius: 12px;
  padding: 24px 16px;
  text-align: center;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.02);
  transition: border-color 120ms ease, background 120ms ease;
  min-height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dropzone--active {
  border-color: #5fd6e8;
  background: rgba(95, 214, 232, 0.08);
}
.dz-link { color: #5fd6e8; }
.dropzone--error {
  border-color: rgba(244, 67, 54, 0.7);
  background: rgba(244, 67, 54, 0.05);
}
.dropzone--ready {
  border-color: rgba(76, 175, 80, 0.7);
  background: rgba(76, 175, 80, 0.05);
}
.dropzone--busy {
  cursor: progress;
}
.dropzone__hint,
.dropzone__progress {
  width: 100%;
}
code {
  background: rgba(255, 255, 255, 0.06);
  padding: 0 4px;
  border-radius: 3px;
}
</style>

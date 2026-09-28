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
          We auto-skip <code>node_modules</code>, <code>.git</code>,
          <code>dist</code>, <code>build</code>. Max total size {{ formatBytes(MAX_TOTAL_BYTES) }}.
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
        <div class="text-subtitle-2 mt-2">{{ scanningLabel }}</div>
        <div v-if="scannedCount > 0" class="text-caption text-grey-lighten-1 mt-1">
          {{ scannedCount }} files seen{{ scanKind === 'zip' ? ' in archive' : '' }}
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
          {{ keptCount }} files · {{ formatBytes(keptSize) }}
          <span v-if="skippedCount > 0">
            · skipped {{ skippedCount }} ({{ formatBytes(skippedSize) }})
          </span>
        </div>
        <div class="text-caption text-grey-lighten-1 mt-1">Click to choose a different source.</div>
      </div>

      <div v-else-if="phase === 'zipping' || phase === 'uploading'" class="dropzone__progress">
        <v-progress-linear
          v-model="progressPercent"
          striped
          height="10"
          color="#5fd6e8"
        />
        <div class="text-caption mt-2">{{ progressLabel }}</div>
        <div v-if="currentFile" class="text-caption text-grey-lighten-2 text-truncate">
          {{ currentFile }}
        </div>
        <v-btn
          size="small"
          variant="text"
          color="error"
          class="mt-2"
          @click.stop="cancel"
        >
          Cancel
        </v-btn>
      </div>

      <div v-else-if="phase === 'analyzing'" class="dropzone__progress">
        <v-progress-circular indeterminate color="#5fd6e8" :size="36" :width="3" />
        <div class="text-caption mt-2">Analyzing on server…</div>
        <div class="text-caption text-grey-lighten-1 mt-1">
          Upload finished — the server is unpacking and validating your dataset.
        </div>
        <v-btn
          size="small"
          variant="text"
          color="error"
          class="mt-2"
          @click.stop="cancel"
        >
          Stop waiting
        </v-btn>
      </div>

      <div v-else-if="phase === 'ready'" class="dropzone__hint">
        <v-icon size="36" color="success">mdi-check-circle-outline</v-icon>
        <div class="text-subtitle-1 mt-1">Source ready.</div>
        <div class="text-caption mt-1">
          Detected: {{ readyDetected }}
        </div>
        <div class="text-caption text-grey-lighten-1 mt-1">
          Click to replace this source.
        </div>
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
  findRootPrefix,
  formatBytes,
  isZipFile,
  traverseEntry,
} from '@/composables/useFolderScan';

export type DropzonePhase =
  | 'idle'
  | 'scanning'
  | 'scanned'
  | 'zipping'
  | 'uploading'
  | 'analyzing'
  | 'ready'
  | 'error';

const props = withDefaults(
  defineProps<{
    /** Detected folders to show in the ready summary (from server response). */
    detectedFolders?: string[];
    /** Detected version to show in the ready summary. */
    detectedVersion?: string;
    /**
     * Per-caller upload ceiling. Tool / workflow defaults to 5 GB; measurement
     * raises it to 20 GB to fit DICOM datasets (matches nginx + backend).
     */
    maxTotalBytes?: number;
  }>(),
  {
    maxTotalBytes: 5 * 1024 * 1024 * 1024,
  },
);

const emit = defineEmits<{
  (e: 'source-selected', source: LocalSource): void;
  (e: 'phase-change', phase: DropzonePhase): void;
  (e: 'cancel-requested'): void;
}>();

// Computed so a parent that fetches the limit at mount can flow it in
// after the dropzone is already alive — non-reactive const would freeze
// the initial default.
const MAX_TOTAL_BYTES = computed(() => props.maxTotalBytes);

const folderInput = ref<HTMLInputElement | null>(null);
const zipInput = ref<HTMLInputElement | null>(null);
const dragActive = ref(false);

const phase = ref<DropzonePhase>('idle');
const scanKind = ref<'folder' | 'zip'>('folder');
const rootName = ref('');
const keptCount = ref(0);
const keptSize = ref(0);
const skippedCount = ref(0);
const skippedSize = ref(0);
const errorMessage = ref('');

// Live counter updated during folder traversal so the user knows we're alive.
const scannedCount = ref(0);

// Progress fields driven by parent via setProgress()
const progressPercent = ref(0);
const currentFile = ref<string | undefined>(undefined);
const uploadLoaded = ref(0);
const uploadTotal = ref(0);

const isBusy = computed(() =>
  phase.value === 'scanning'
    || phase.value === 'zipping'
    || phase.value === 'uploading'
    || phase.value === 'analyzing',
);

const scanningLabel = computed(() => {
  if (scanKind.value === 'zip') return 'Reading archive…';
  return 'Scanning folder…';
});

const progressLabel = computed(() => {
  if (phase.value === 'zipping') {
    return `Packaging your folder… ${Math.round(progressPercent.value)}%`;
  }
  if (phase.value === 'uploading') {
    return `Uploading… ${formatBytes(uploadLoaded.value)} / ${formatBytes(uploadTotal.value)} · ${Math.round(progressPercent.value)}%`;
  }
  return '';
});

const readyDetected = computed(() => {
  const parts: string[] = [];
  if (props.detectedFolders && props.detectedFolders.length > 0) {
    parts.push(props.detectedFolders.join(', '));
  }
  if (props.detectedVersion) {
    parts.push(`package.json v${props.detectedVersion}`);
  }
  return parts.join(' · ') || 'source archive';
});

function setPhase(next: DropzonePhase) {
  phase.value = next;
  emit('phase-change', next);
}

/**
 * Wait for the browser to actually paint the new phase before continuing.
 * `requestAnimationFrame` guarantees the browser has had a chance to render
 * since the last reactive update, and the small timeout enforces a minimum
 * visible duration so the spinner doesn't blink past for tiny inputs.
 */
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
  currentFile.value = undefined;
  uploadLoaded.value = 0;
  uploadTotal.value = 0;
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

// ---- Drop / input change handlers ----------------------------------------
async function onDrop(ev: DragEvent) {
  dragActive.value = false;
  if (!ev.dataTransfer) return;
  if (isBusy.value) return;

  // CRITICAL: snapshot DataTransfer state SYNCHRONOUSLY before any await
  // (captureDataTransfer does this) — once this handler yields, items are
  // cleared and webkitGetAsEntry returns null.
  const { flatFiles, captured } = captureDataTransfer(ev.dataTransfer);

  // Single .zip file → zip path.
  if (flatFiles.length === 1 && isZipFile(flatFiles[0])) {
    await handleZipFile(flatFiles[0]);
    return;
  }

  // Folder mode — safe to async now that entries are captured.
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
  // <input webkitdirectory> hands us the FileList synchronously, but we still
  // pause so the spinner becomes visible — otherwise the phase flips before
  // the browser ever paints it.
  await yieldToPaint();
  finalizeFolderScan(files);
}

async function onZipInputChange(ev: Event) {
  const target = ev.target as HTMLInputElement;
  const f = target.files?.[0];
  if (!f) return;
  await handleZipFile(f);
}

// ---- Folder scan finalization --------------------------------------------
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

// ---- Zip file handling ----------------------------------------------------
async function handleZipFile(file: File) {
  reset();
  scanKind.value = 'zip';
  setPhase('scanning');
  // Two paint windows: one before size check (instant feedback), one after
  // we kick off JSZip (which itself yields, so the spinner stays animated).
  await yieldToPaint();

  if (file.size > MAX_TOTAL_BYTES.value) {
    errorMessage.value = `Archive is ${formatBytes(file.size)} — exceeds the ${formatBytes(MAX_TOTAL_BYTES.value)} upload limit.`;
    setPhase('error');
    return;
  }

  let JSZipMod: typeof import('jszip').default;
  try {
    JSZipMod = (await import('jszip')).default;
  } catch (err) {
    console.error('Failed to load JSZip:', err);
    errorMessage.value = 'Could not load zip parser. Please refresh and try again.';
    setPhase('error');
    return;
  }

  let entries: Record<string, { dir: boolean }>;
  try {
    const zip = await JSZipMod.loadAsync(file);
    entries = zip.files as Record<string, { dir: boolean }>;
  } catch (err) {
    console.error('Failed to read zip:', err);
    errorMessage.value = 'That zip file could not be read. Is it a valid archive?';
    setPhase('error');
    return;
  }

  const allPaths = Object.keys(entries);
  const fileCount = allPaths.filter((p) => !entries[p].dir).length;
  scannedCount.value = fileCount;

  // Recursive wrapper detection — peels nested `outer/inner/project/...`
  // chains so the displayed root + the upload pipeline agree on what the
  // real project root is. Exactly mirrors the backend's `resolve_project_root`.
  const entriesArr = allPaths.map((p) => ({ path: p, isDir: entries[p].dir }));
  const prefix = findRootPrefix(entriesArr); // "outer/inner/" or ""
  const segments = prefix.replace(/\/$/, '').split('/').filter(Boolean);
  const deepestWrapper = segments[segments.length - 1] ?? '';
  // Prefer the deepest folder name (the actual project) over the zip filename;
  // for rootless zips fall back to the user-friendly zip filename minus .zip.
  rootName.value = deepestWrapper || file.name.replace(/\.zip$/i, '');

  keptCount.value = fileCount;
  keptSize.value = file.size; // compressed size — best signal we have client-side
  skippedCount.value = 0;
  skippedSize.value = 0;

  setPhase('scanned');
  emit('source-selected', {
    kind: 'zip',
    blob: file,
    rootName: rootName.value,
    fileCount,
    totalSize: file.size,
  });
}

function cancel() {
  // `analyzing` is included: the bytes are already sent, so this aborts the
  // client's wait for the response rather than the transfer. The backend's
  // orphaned staging dir is reaped by the tmp/ orphan cleanup, so nothing is
  // left behind as a dataset (the user never reached /create).
  if (phase.value === 'zipping' || phase.value === 'uploading' || phase.value === 'analyzing') {
    emit('cancel-requested');
    setPhase('idle');
    reset();
  }
}

// ---- API exposed to parent (via defineExpose) -----------------------------
function setProgress(p:
  | { phase: 'zip'; percent: number; currentFile?: string }
  | { phase: 'upload'; loaded: number; total: number; percent: number }
  | { phase: 'server' }
  | { phase: 'ready' }
  | { phase: 'error'; message: string }
  | { phase: 'reset' }
) {
  if (p.phase === 'zip') {
    setPhase('zipping');
    progressPercent.value = p.percent;
    currentFile.value = p.currentFile;
    return;
  }
  if (p.phase === 'upload') {
    setPhase('uploading');
    progressPercent.value = p.percent;
    uploadLoaded.value = p.loaded;
    uploadTotal.value = p.total;
    currentFile.value = undefined;
    return;
  }
  if (p.phase === 'server') {
    setPhase('analyzing');
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

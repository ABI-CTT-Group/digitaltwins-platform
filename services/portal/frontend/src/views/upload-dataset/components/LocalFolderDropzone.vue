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
        <v-icon size="42" color="cyan-lighten-2">mdi-folder-upload-outline</v-icon>
        <div class="text-h6 mt-2">Drag a folder or a .zip file here, or click to browse</div>
        <div class="text-caption text-grey-lighten-1 mt-1">
          We auto-skip <code>node_modules</code>, <code>.git</code>,
          <code>dist</code>, <code>build</code>. Max total size 500 MB.
        </div>
        <a
          href="#"
          class="text-caption text-cyan-lighten-2 mt-2 d-inline-block"
          @click.stop.prevent="triggerZipInput"
        >
          Or pick a .zip file
        </a>
      </div>

      <div v-else-if="phase === 'scanning'" class="dropzone__progress">
        <v-progress-circular indeterminate color="cyan" :size="36" :width="3" />
        <div class="text-subtitle-2 mt-2">{{ scanningLabel }}</div>
        <div v-if="scannedCount > 0" class="text-caption text-grey-lighten-1 mt-1">
          {{ scannedCount }} files seen{{ scanKind === 'zip' ? ' in archive' : '' }}
        </div>
      </div>

      <div v-else-if="phase === 'scanned'" class="dropzone__hint">
        <v-icon size="36" :color="scanKind === 'zip' ? 'cyan-lighten-2' : 'cyan-lighten-2'">
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
          color="cyan"
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
        <v-progress-circular indeterminate color="cyan" :size="36" :width="3" />
        <div class="text-caption mt-2">Analyzing on server…</div>
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

export type DropzonePhase =
  | 'idle'
  | 'scanning'
  | 'scanned'
  | 'zipping'
  | 'uploading'
  | 'analyzing'
  | 'ready'
  | 'error';

const props = defineProps<{
  /** Detected folders to show in the ready summary (from server response). */
  detectedFolders?: string[];
  /** Detected version to show in the ready summary. */
  detectedVersion?: string;
}>();

const emit = defineEmits<{
  (e: 'source-selected', source: LocalSource): void;
  (e: 'phase-change', phase: DropzonePhase): void;
  (e: 'cancel-requested'): void;
}>();

const MAX_TOTAL_BYTES = 500 * 1024 * 1024;
const FOLDER_BLACKLIST = new Set(['node_modules', '.git', 'dist', 'build']);

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

function isBlacklisted(relPath: string): boolean {
  return relPath.split('/').some((seg) => FOLDER_BLACKLIST.has(seg));
}

function isZipFile(f: File): boolean {
  return f.name.toLowerCase().endsWith('.zip')
    || f.type === 'application/zip'
    || f.type === 'application/x-zip-compressed';
}

function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '0 B';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

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

/**
 * Recursive single-wrapper detection. Mirrors the backend's
 * `resolve_project_root`: peels nested `outer/inner/project/...` chains until
 * we hit a level that contains either multiple top-level dirs OR any
 * top-level files. Returns the prefix to strip (with trailing slash) or `""`.
 */
function findRootPrefix(entries: { path: string; isDir: boolean }[]): string {
  let prefix = '';
  for (let depth = 0; depth < 20; depth++) {
    const topDirs = new Set<string>();
    const topFiles = new Set<string>();
    for (const e of entries) {
      if (e.path === '__MACOSX' || e.path.startsWith('__MACOSX/')) continue;
      if (prefix && !e.path.startsWith(prefix)) continue;
      const rel = prefix ? e.path.slice(prefix.length) : e.path;
      if (!rel) continue;
      const trimmed = rel.replace(/\/$/, '');
      if (!trimmed) continue;
      const segments = trimmed.split('/');
      if (!segments[0]) continue;
      if (segments.length === 1) {
        if (e.isDir) topDirs.add(segments[0]);
        else topFiles.add(segments[0]);
      } else {
        topDirs.add(segments[0]);
      }
    }
    if (topDirs.size === 1 && topFiles.size === 0) {
      prefix += `${Array.from(topDirs)[0]}/`;
    } else {
      break;
    }
  }
  return prefix;
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

// ---- Folder traversal (drag-drop case) ------------------------------------
// `webkitGetAsEntry` exposes a tree we walk recursively. We periodically
// yield to the event loop so the spinner + counter actually animate.
async function traverseEntry(entry: any, out: File[], pathPrefix: string): Promise<void> {
  if (entry.isFile) {
    await new Promise<void>((resolve) => {
      entry.file((file: File) => {
        const relPath = pathPrefix ? `${pathPrefix}/${entry.name}` : entry.name;
        try {
          Object.defineProperty(file, 'webkitRelativePath', {
            value: relPath,
            configurable: true,
          });
        } catch {
          // Some browsers won't let us redefine; ignore.
        }
        out.push(file);
        resolve();
      });
    });
    // Bump the live counter and yield every 25 files so the UI repaints.
    if (out.length % 25 === 0) {
      scannedCount.value = out.length;
      await new Promise((r) => setTimeout(r, 0));
    }
    return;
  }
  if (entry.isDirectory) {
    const reader = entry.createReader();
    const children: any[] = await new Promise((resolve) => {
      const all: any[] = [];
      const readBatch = () =>
        reader.readEntries((batch: any[]) => {
          if (batch.length === 0) resolve(all);
          else {
            all.push(...batch);
            readBatch();
          }
        });
      readBatch();
    });
    const nextPrefix = pathPrefix ? `${pathPrefix}/${entry.name}` : entry.name;
    for (const child of children) {
      await traverseEntry(child, out, nextPrefix);
    }
  }
}

// ---- Drop / input change handlers ----------------------------------------
async function onDrop(ev: DragEvent) {
  dragActive.value = false;
  if (!ev.dataTransfer) return;
  if (isBusy.value) return;

  // CRITICAL: snapshot DataTransfer state SYNCHRONOUSLY before any await.
  // Once this handler yields, `dataTransfer.items` is cleared by the browser
  // and `webkitGetAsEntry()` returns null — we'd silently get zero files.
  // FileSystemEntry refs and File objects survive across awaits; the act of
  // *obtaining* them is what must happen sync.
  const dt = ev.dataTransfer;
  const flatFiles = Array.from(dt.files);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const captured: { entry?: any; file?: File }[] = [];
  for (let i = 0; i < dt.items.length; i++) {
    const item = dt.items[i];
    if (item.kind !== 'file') continue;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const entry: any = (item as any).webkitGetAsEntry?.();
    if (entry) {
      captured.push({ entry });
    } else {
      const f = item.getAsFile();
      if (f) captured.push({ file: f });
    }
  }

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
        await traverseEntry(c.entry, out, '');
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

  const kept: File[] = [];
  let keptS = 0;
  let skippedC = 0;
  let skippedS = 0;

  for (const f of files) {
    const relPath = f.webkitRelativePath || f.name;
    if (isBlacklisted(relPath)) {
      skippedC += 1;
      skippedS += f.size;
      continue;
    }
    kept.push(f);
    keptS += f.size;
  }

  if (kept.length === 0) {
    errorMessage.value = 'No files left after filtering. Did you drop an empty or fully-skipped folder?';
    setPhase('error');
    return;
  }

  if (keptS > MAX_TOTAL_BYTES) {
    errorMessage.value = `Folder is ${formatBytes(keptS)} after filtering — exceeds the 500 MB upload limit.`;
    setPhase('error');
    return;
  }

  const firstRelPath = kept[0].webkitRelativePath || kept[0].name;
  const root = firstRelPath.includes('/') ? firstRelPath.split('/')[0] : '';
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

  if (file.size > MAX_TOTAL_BYTES) {
    errorMessage.value = `Archive is ${formatBytes(file.size)} — exceeds the 500 MB upload limit.`;
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
  if (phase.value === 'zipping' || phase.value === 'uploading') {
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
  border-color: var(--v-theme-cyan, #4dd0e1);
  background: rgba(77, 208, 225, 0.08);
}
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

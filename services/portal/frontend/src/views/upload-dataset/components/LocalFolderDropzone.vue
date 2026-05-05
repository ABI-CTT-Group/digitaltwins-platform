<template>
  <div class="folder-dropzone-wrapper">
    <div
      class="dropzone"
      :class="{
        'dropzone--active': dragActive,
        'dropzone--error': phase === 'error',
        'dropzone--ready': phase === 'ready',
      }"
      @dragover.prevent="onDragOver"
      @dragleave.prevent="dragActive = false"
      @drop.prevent="onDrop"
      @click="triggerInput"
    >
      <input
        ref="fileInput"
        type="file"
        multiple
        webkitdirectory
        directory
        style="display: none"
        @change="onInputChange"
      />

      <div v-if="phase === 'idle'" class="dropzone__hint">
        <v-icon size="42" color="cyan-lighten-2">mdi-folder-upload-outline</v-icon>
        <div class="text-h6 mt-2">Drag a folder here, or click to browse</div>
        <div class="text-caption text-grey-lighten-1 mt-1">
          We auto-skip <code>node_modules</code>, <code>.git</code>,
          <code>dist</code>, <code>build</code>. Max total size 500 MB.
        </div>
      </div>

      <div v-else-if="phase === 'scanned'" class="dropzone__hint">
        <v-icon size="36" color="cyan-lighten-2">mdi-folder-check-outline</v-icon>
        <div class="text-subtitle-1 mt-1">{{ rootName || 'Folder selected' }}</div>
        <div class="text-caption mt-1">
          Found {{ keptCount }} files · {{ formatBytes(keptSize) }}
          <span v-if="skippedCount > 0">
            · skipped {{ skippedCount }} ({{ formatBytes(skippedSize) }})
          </span>
        </div>
        <div class="text-caption text-grey-lighten-1 mt-1">Click to choose a different folder.</div>
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
        <v-progress-circular indeterminate color="cyan" />
        <div class="text-caption mt-2">Analyzing on server…</div>
      </div>

      <div v-else-if="phase === 'ready'" class="dropzone__hint">
        <v-icon size="36" color="success">mdi-check-circle-outline</v-icon>
        <div class="text-subtitle-1 mt-1">Source ready.</div>
        <div class="text-caption mt-1">
          Detected: {{ readyDetected }}
        </div>
        <div class="text-caption text-grey-lighten-1 mt-1">
          Click to replace this folder.
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

export type DropzonePhase =
  | 'idle'
  | 'scanned'
  | 'zipping'
  | 'uploading'
  | 'analyzing'
  | 'ready'
  | 'error';

const props = defineProps<{
  /** When true, the parent has finished server-side processing successfully. */
  ready?: boolean;
  /** Detected folders to show in the ready summary. */
  detectedFolders?: string[];
  /** Detected version to show in the ready summary. */
  detectedVersion?: string;
}>();

const emit = defineEmits<{
  (e: 'folder-selected', files: File[]): void;
  (e: 'phase-change', phase: DropzonePhase): void;
  (e: 'cancel-requested'): void;
}>();

const MAX_TOTAL_BYTES = 500 * 1024 * 1024;
const FOLDER_BLACKLIST = new Set(['node_modules', '.git', 'dist', 'build']);

const fileInput = ref<HTMLInputElement | null>(null);
const dragActive = ref(false);

const phase = ref<DropzonePhase>('idle');
const rootName = ref('');
const keptCount = ref(0);
const keptSize = ref(0);
const skippedCount = ref(0);
const skippedSize = ref(0);
const errorMessage = ref('');

// Progress fields driven by parent via setProgress()
const progressPercent = ref(0);
const currentFile = ref<string | undefined>(undefined);
const uploadLoaded = ref(0);
const uploadTotal = ref(0);

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

function reset() {
  rootName.value = '';
  keptCount.value = 0;
  keptSize.value = 0;
  skippedCount.value = 0;
  skippedSize.value = 0;
  progressPercent.value = 0;
  currentFile.value = undefined;
  uploadLoaded.value = 0;
  uploadTotal.value = 0;
  errorMessage.value = '';
  if (fileInput.value) fileInput.value.value = '';
}

function triggerInput() {
  if (phase.value === 'zipping' || phase.value === 'uploading' || phase.value === 'analyzing') {
    return;
  }
  fileInput.value?.click();
}

function onDragOver() {
  if (phase.value === 'zipping' || phase.value === 'uploading' || phase.value === 'analyzing') {
    return;
  }
  dragActive.value = true;
}

async function collectFromDataTransferItem(
  item: DataTransferItem,
  out: File[],
  pathPrefix: string,
): Promise<void> {
  // Use webkitGetAsEntry for directory recursion when a folder is dropped.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const entry: any = (item as any).webkitGetAsEntry?.();
  if (!entry) {
    const f = item.getAsFile();
    if (f) out.push(f);
    return;
  }
  await traverseEntry(entry, out, pathPrefix);
}

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
          // ignore — Chrome lets us redefine; some browsers may not
        }
        out.push(file);
        resolve();
      });
    });
    return;
  }
  if (entry.isDirectory) {
    const reader = entry.createReader();
    const childEntries: any[] = await new Promise((resolve) => {
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
    for (const child of childEntries) {
      await traverseEntry(child, out, nextPrefix);
    }
  }
}

async function onDrop(ev: DragEvent) {
  dragActive.value = false;
  if (!ev.dataTransfer) return;
  const items = Array.from(ev.dataTransfer.items);
  const collected: File[] = [];
  for (const item of items) {
    await collectFromDataTransferItem(item, collected, '');
  }
  handleFiles(collected);
}

function onInputChange(ev: Event) {
  const target = ev.target as HTMLInputElement;
  if (!target.files) return;
  handleFiles(Array.from(target.files));
}

function handleFiles(files: File[]) {
  if (files.length === 0) return;
  reset();

  let kept: File[] = [];
  let skippedC = 0;
  let skippedS = 0;
  let keptS = 0;

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
  rootName.value = firstRelPath.split('/')[0] ?? '';
  keptCount.value = kept.length;
  keptSize.value = keptS;
  skippedCount.value = skippedC;
  skippedSize.value = skippedS;

  setPhase('scanned');
  emit('folder-selected', kept);
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
.dropzone__hint {
  width: 100%;
}
.dropzone__progress {
  width: 100%;
}
code {
  background: rgba(255, 255, 255, 0.06);
  padding: 0 4px;
  border-radius: 3px;
}
</style>

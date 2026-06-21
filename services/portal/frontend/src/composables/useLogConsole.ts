import { ref } from 'vue';

/**
 * Shared, app-level state for the build/deploy LogConsole modal.
 *
 * The console must be openable from BOTH the registration wizard
 * (UploadToolForm — first build) and the tool hub (ToolsOverallView —
 * rebuild / deploy / View-logs), which are mutually-exclusive `v-if`/`v-else`
 * views. Mounting <LogConsole> inside either one means the other can't open
 * it. So the state lives here as a module-level singleton and a single
 * <LogConsole> is mounted once at the workflow-tool index.vue level.
 *
 * Host-app composable (not a plugin) — a module-level singleton is fine.
 */
const open = ref(false);
const kind = ref<'build' | 'deploy'>('build');
const jobId = ref('');
const title = ref('');
const startedAt = ref('');
const initialStatus = ref('');

export function useLogConsole() {
  /**
   * Open the console for a build/deploy job.
   * @param startedAtIso optional ISO start time (for reopening an existing
   *   job); omit for a freshly-triggered job to start the timer from now.
   */
  function openConsole(
    k: 'build' | 'deploy',
    id: string,
    t: string,
    status: string,
    startedAtIso?: string,
  ) {
    if (!id) return; // never open against an empty job id (would 404 the SSE)
    kind.value = k;
    jobId.value = id;
    title.value = t;
    startedAt.value = startedAtIso ?? new Date().toISOString();
    initialStatus.value = status;
    open.value = true;
  }

  return { open, kind, jobId, title, startedAt, initialStatus, openConsole };
}

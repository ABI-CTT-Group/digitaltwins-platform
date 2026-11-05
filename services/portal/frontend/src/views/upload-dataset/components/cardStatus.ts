/**
 * What a catalogue card says about its item: one status sentence, one next step, and chips only for
 * problems (docs/decisions/2026-11-06-card-status-sentence.md). Pure, so each state table row is a test.
 *
 * Tone follows "quiet when fine, loud when not": steady (uncoloured), running (pale), needs (amber),
 * failed (coral). Group feeds the hub filter: needs (you have something to do), progress (running),
 * platform (in the platform, nothing wrong), other (none of these).
 */
import type { MeasurementResponse, ToolResponse, WorkflowResponse } from '@/models/types';

export type Tone = 'steady' | 'running' | 'needs' | 'failed';
export type HubGroup = 'needs' | 'progress' | 'platform' | 'other';
export type CardAction =
  | 'build' | 'view-logs' | 'approve' | 'approve-again' | 'launch' | 'deploy-dag' | 'retry-fhir' | 'resume-upload';

export interface CardProblem { label: string; reason?: string }

export interface CardStatus {
  sentence: string;
  /** Why it failed, shown under the sentence (in full on hover). */
  reason?: string;
  /** What to do next, shown under the sentence when there is no reason. */
  hint?: string;
  tone: Tone;
  group: HubGroup;
  action?: CardAction;
  problems: CardProblem[];
}

export const ACTION_LABELS: Record<CardAction, string> = {
  'build': 'Build',
  'view-logs': 'View logs',
  'approve': 'Approve',
  'approve-again': 'Approve again',
  'launch': 'Launch',
  'deploy-dag': 'Deploy DAG',
  'retry-fhir': 'Retry FHIR',
  'resume-upload': 'Resume upload',
};

const HANDOFF_ACTIVE = ['uploading', 'committing'];
const APPROVE_HINT = 'Approve it so assays can use it.';

const status = (sentence: string, tone: Tone, group: HubGroup, extra: Partial<CardStatus> = {}): CardStatus =>
  ({ sentence, tone, group, problems: [], ...extra });

/** A real platform dataset: uploaded straight to the platform, or a uuid that isn't a legacy placeholder. */
export const isInPlatform = (item: { uuid?: string; platformOnly?: boolean }, placeholderPrefix: string) =>
  !!item.platformOnly || (!!item.uuid && !item.uuid.startsWith(placeholderPrefix));

type Built = Pick<ToolResponse, 'status' | 'latestBuildId' | 'platformOnly' | 'uuid' | 'handoffStatus' | 'handoffError'
  | 'fhirStatus' | 'fhirFailureMessage'> & { buildError?: string | null };

/**
 * The states tools and workflows share, in order: approving, not built, building, build failed,
 * approval failed. Returns null once the item is built and not being approved.
 */
function buildAndApproval(item: Built, inPlatform: boolean, { logs, build }: { logs: boolean; build: boolean }): CardStatus | null {
  if (HANDOFF_ACTIVE.includes(item.handoffStatus ?? '')) return status('Approving…', 'running', 'progress');
  if (item.handoffStatus === 'awaiting_reauth') return status('Approving… waiting for you to sign in again', 'needs', 'needs');
  if (item.platformOnly) return null;
  const viewLogs = logs ? { action: 'view-logs' as const } : {};
  if (!item.latestBuildId) return status('Not built yet', 'needs', 'needs', build ? { action: 'build' } : {});
  if (item.status === 'building' || item.status === 'pending') {
    return status(inPlatform ? 'In the platform — rebuilding…' : 'Building…', 'running', 'progress', viewLogs);
  }
  if (item.status === 'failed' && !inPlatform) {
    return status('Build failed', 'failed', 'needs', { reason: item.buildError ?? undefined, ...viewLogs });
  }
  if (item.handoffStatus === 'failed' && !inPlatform) {
    return status('Approval failed', 'failed', 'needs', { reason: item.handoffError, action: 'approve-again' });
  }
  return null;
}

/**
 * In the platform: problems become chips, and the most urgent one picks the sentence and the action.
 * `launch` is the action when nothing needs fixing (a GUI tool).
 */
function inPlatformStatus(item: Built, problems: CardProblem[], idle?: CardAction, approvable = !item.platformOnly): CardStatus {
  if (approvable && item.status === 'failed') problems.unshift({ label: 'rebuild failed', reason: item.buildError ?? undefined });
  if (approvable && item.handoffStatus === 'failed') {
    problems.unshift({ label: 're-approval failed', reason: item.handoffError });
    return status('In the platform', 'steady', 'needs', { problems, action: 'approve-again' });
  }
  if (item.fhirStatus === 'failed') {
    return status('In the platform — FHIR publishing failed', 'failed', 'needs',
      { reason: item.fhirFailureMessage, action: 'retry-fhir', problems });
  }
  // The latest build completed but was never handed to the platform: the platform runs an older one.
  if (approvable && item.status === 'completed' && !item.handoffStatus) {
    return status("In the platform — a newer build isn't approved yet", 'needs', 'needs', { action: 'approve', problems });
  }
  return status('In the platform', 'steady', problems.length ? 'needs' : 'platform', { problems, action: idle });
}

export function toolStatus(t: ToolResponse & { buildError?: string | null; deployError?: string | null }): CardStatus {
  const inPlatform = t.kind === 'workflow' ? !!t.uuid : isInPlatform(t, 'sparc-tool-');
  const launch = t.label === 'GUI' && !t.platformOnly ? 'launch' as const : undefined;

  // A gui workflow's tool: its workflow builds and approves it, so only the served build's state shows.
  if (t.kind === 'workflow') {
    if (t.status === 'building' || t.status === 'pending') return status('Building…', 'running', 'progress');
    if (!inPlatform) {
      return status('Built — not in the platform yet', 'needs', 'needs',
        { hint: `Approve ${t.workflowName ?? 'its workflow'} in Workflows to add it to the platform.` });
    }
    return inPlatformStatus(t, backendProblems(t), launch, false);
  }

  const early = buildAndApproval(t, inPlatform, { logs: true, build: true });
  if (early) return early;
  if (!inPlatform) return status('Built — not in the platform yet', 'needs', 'needs', { hint: APPROVE_HINT, action: 'approve' });
  return inPlatformStatus(t, backendProblems(t), launch);
}

function backendProblems(t: ToolResponse & { deployError?: string | null }): CardProblem[] {
  return t.deployStatus === 'failed' ? [{ label: 'backend failed', reason: t.deployError ?? undefined }] : [];
}

export function workflowStatus(
  w: WorkflowResponse & { buildError?: string | null },
  { canDeploy = false }: { canDeploy?: boolean } = {},
): CardStatus {
  const inPlatform = isInPlatform(w, 'sparc-workflow-');
  // The Workflow Hub has no log console, and reopening a closed wizard comes with its own route.
  const early = buildAndApproval(w, inPlatform, { logs: false, build: false });
  if (early) return early;
  if (!inPlatform) {
    // follow-up: non-SDS workflows, not supported for now (docs/decisions/2026-11-06-card-status-sentence.md).
    if (w.isSds !== true) return status('Not an SDS package — not supported yet', 'steady', 'other');
    return status('Built — not in the platform yet', 'needs', 'needs', { hint: APPROVE_HINT, action: 'approve' });
  }

  const script = w.workflowType === 'script';
  if (script && w.dagStatus === 'deploying') return status('In the platform — deploying the DAG…', 'running', 'progress');
  const problems: CardProblem[] = script && w.dagStatus === 'failed'
    ? [{ label: 'DAG deploy failed', reason: w.dagError ?? undefined }] : [];
  const deploy = canDeploy && script && w.dagStatus !== 'deployed' ? 'deploy-dag' as const : undefined;
  return inPlatformStatus(w, problems, deploy);
}

/** A measurement or model, from measurement_api's adapted status. */
export function datasetStatus(m: Pick<MeasurementResponse, 'status' | 'uuid' | 'failureMessage'>): CardStatus {
  // Committed: the files are stored, whatever the FHIR push is doing.
  if (m.uuid) {
    if (m.status === 'fhir_failed') {
      return status('In the platform — FHIR publishing failed', 'failed', 'needs', { reason: m.failureMessage, action: 'retry-fhir' });
    }
    if (m.status === 'uploading') return status('In the platform — publishing to FHIR…', 'running', 'progress');
    return status('In the platform', 'steady', 'platform');
  }
  switch (m.status) {
    case 'pending_upload': return status('Upload paused', 'needs', 'needs', { action: 'resume-upload' });
    case 'uploading': return status('Approving…', 'running', 'progress');
    case 'submit_failed': return status('Approval failed', 'failed', 'needs', { reason: m.failureMessage, action: 'approve-again' });
    default: return status('Ready to approve', 'needs', 'needs', { hint: APPROVE_HINT, action: 'approve' });
  }
}

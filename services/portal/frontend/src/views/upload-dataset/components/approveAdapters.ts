/**
 * Approval, the same for every hub (ApproveDialog.vue): start it, then poll it to an end. Tools and SDS workflows
 * hand their latest build to the platform in a SEEK project (the builder's handoff); measurements and models commit
 * their staged upload. Both read as one progress shape.
 * One rule for FHIR: an item with an annotation is published to FHIR, one without isn't
 * (docs/decisions/2026-11-06-optional-fhir-annotation.md).
 */
import { usePlatformDataset, useToolApproval, useToolApprovalStatus } from '@/bootstrap/tool_api';
import { useWorkflowApprovalStatus, useWorkflowPlatformApproval } from '@/bootstrap/workflow_api';
import { useGetMeasurement, useMeasurementSubmit } from '@/bootstrap/measurement_api';
import type { MeasurementResponse, ToolApprovalStatus } from '@/models/types';

export type ApproveCategory = 'tools' | 'workflows' | 'measurements' | 'models';

export interface ApprovalProgress {
  /** running and waiting go on; done and failed are the end. */
  state: 'running' | 'waiting' | 'done' | 'failed';
  stage: string;
  /** Upload progress, when the handoff reports parts. */
  percent?: number;
  /** Why it failed. */
  error?: string;
  /** Done, but its FHIR push failed: the card retries it. */
  fhirError?: string;
}

export interface ApproveAdapter {
  /** Tools and workflows are registered in a SEEK project. */
  needsProject: boolean;
  start(item: { id: string; hasAnnotation?: boolean }, seekProjectId?: number): Promise<ApprovalProgress>;
  poll(item: { id: string }): Promise<ApprovalProgress>;
}

const IN_PLATFORM = 'In the platform';
const FHIR_RUNNING = ['pending', 'pushing'];

function handoffProgress(s: ToolApprovalStatus): ApprovalProgress {
  switch (s.handoffStatus) {
    case 'uploading':
      return { state: 'running', stage: 'Uploading the build',
        ...(s.partsTotal ? { percent: Math.round((100 * (s.partsSent ?? 0)) / s.partsTotal) } : {}) };
    case 'committing': return { state: 'running', stage: 'Registering it in SEEK and storing it in the platform' };
    case 'awaiting_reauth': return { state: 'waiting', stage: 'Waiting for you to sign in again' };
    case 'failed': return { state: 'failed', stage: 'Approval failed', error: s.handoffError };
    case 'completed': return { state: 'done', stage: IN_PLATFORM };
    default: return { state: 'running', stage: 'Starting' };
  }
}

/** Once the build is in the platform, its FHIR push runs on: follow it too. */
async function withFhir(s: ToolApprovalStatus): Promise<ApprovalProgress> {
  const progress = handoffProgress(s);
  if (progress.state !== 'done' || !s.datasetUuid) return progress;
  try {
    const dataset = await usePlatformDataset(s.datasetUuid);
    if (FHIR_RUNNING.includes(dataset.fhirStatus ?? '')) return { state: 'running', stage: 'Publishing to FHIR' };
    if (dataset.fhirStatus === 'failed') return { ...progress, fhirError: dataset.fhirFailureMessage || 'FHIR publishing failed' };
  } catch (err) {
    console.warn('Could not read the platform dataset:', err);
  }
  return progress;
}

function handoff(approve: typeof useToolApproval, status: typeof useToolApprovalStatus): ApproveAdapter {
  return {
    needsProject: true,
    // Without an annotation the handoff sends no FHIR descriptions, so nothing is published (as for datasets).
    start: async (item, seekProjectId) =>
      withFhir(await approve(item.id, { seekProjectId, fhir: !!item.hasAnnotation })),
    poll: async (item) => withFhir(await status(item.id)),
  };
}

function datasetProgress(m: MeasurementResponse): ApprovalProgress {
  if (m.uuid && m.status === 'uploading') return { state: 'running', stage: 'Publishing to FHIR' };
  switch (m.status) {
    case 'completed': return { state: 'done', stage: IN_PLATFORM };
    case 'fhir_failed': return { state: 'done', stage: IN_PLATFORM, fhirError: m.failureMessage || 'FHIR publishing failed' };
    case 'submit_failed': return { state: 'failed', stage: 'Approval failed', error: m.failureMessage };
    case 'uploading': return { state: 'running', stage: 'Storing it in the platform' };
    default: return { state: 'running', stage: 'Starting' };
  }
}

const upload: ApproveAdapter = {
  needsProject: false,
  start: async (item) => datasetProgress(await useMeasurementSubmit(item.id)),
  poll: async (item) => datasetProgress(await useGetMeasurement(item.id)),
};

export function approveAdapter(category: ApproveCategory): ApproveAdapter {
  if (category === 'tools') return handoff(useToolApproval, useToolApprovalStatus);
  if (category === 'workflows') return handoff(useWorkflowPlatformApproval, useWorkflowApprovalStatus);
  return upload;
}

/** The confirm step's one line about FHIR, for an item with no annotation; nothing when it has one. */
export function fhirHint(category: ApproveCategory, item: { hasAnnotation?: boolean }): string | undefined {
  if (item.hasAnnotation) return undefined;
  // A model's card can add an annotation after approval; the portal annotates the others only before it.
  return category === 'models'
    ? 'No FHIR annotation, so nothing is published to FHIR. You can add one later from its card.'
    : 'No FHIR annotation, so nothing is published to FHIR. To publish it, add one before approving.';
}

/** What approving does, in the confirm step. */
export const APPROVE_INTRO: Record<ApproveCategory, string> = {
  tools: 'Its latest build is registered in SEEK as you and stored in the platform, so workflows and assays can use it. '
    + 'Approving a rebuild replaces the version in the platform.',
  workflows: 'Its latest build is registered in SEEK as you and stored in the platform, with a tool dataset for each of its tools, '
    + 'so assays can run it. Approving a rebuild replaces the version in the platform.',
  measurements: 'The dataset is stored in the platform, so assays can use it as an input. To change it afterwards, delete it and register it again.',
  models: 'The model is stored in the platform, so assays and inference workflows can use it by its dataset UUID.',
};

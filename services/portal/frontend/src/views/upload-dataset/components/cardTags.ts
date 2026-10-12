/**
 * Card tags shared by the four dataset hubs (Measurements, Models, Tools, Workflows),
 * so one word means one state everywhere:
 *
 *  - Registration (every card): upload paused · draft · registering… ·
 *    registration failed · in platform (amber when FHIR or a re-approval failed).
 *  - `build · <status>` (portal-built tools and workflows).
 *  - Type: gui · script · notebook (tools and workflows).
 *
 * Colours: grey waits for the user, cyan runs, green is done, red failed,
 * amber is done but needs attention. A red or amber tag's `title` says why.
 */
import type { MeasurementResponse, HandoffStatus } from '@/models/types';

export interface CardTag {
  label: string;
  color?: string;
  title?: string;
}

const GREY = '#9fb4bf';
const CYAN = '#5fd6e8';
const GREEN = '#6fd49a';
const RED = '#ff6b6b';
const AMBER = '#ffb74d';

const withTitle = (tag: CardTag, title?: string): CardTag => (title ? { ...tag, title } : tag);
const fhirFailed = (message?: string) => (message ? `FHIR publishing failed: ${message}` : 'FHIR publishing failed');

/** Registration of a measurement or model, from measurement_api's adapted status. */
export function measurementRegistrationTag(
  m: Pick<MeasurementResponse, 'status' | 'uuid' | 'failureMessage'>,
): CardTag {
  // Committed: the files are stored, whatever the FHIR push is doing.
  if (m.uuid) {
    return m.status === 'fhir_failed'
      ? { label: 'in platform', color: AMBER, title: fhirFailed(m.failureMessage) }
      : { label: 'in platform', color: GREEN };
  }
  switch (m.status) {
    case 'pending_upload': return { label: 'upload paused', color: GREY };
    case 'uploading': return { label: 'registering…', color: CYAN };
    case 'submit_failed': return withTitle({ label: 'registration failed', color: RED }, m.failureMessage);
    default: return { label: 'draft', color: GREY };
  }
}

const HANDOFF_ACTIVE = ['uploading', 'awaiting_reauth', 'committing'];

/** Registration of a tool or workflow, from its approval handoff to the platform. */
export function handoffRegistrationTag(
  item: {
    uuid?: string;
    platformOnly?: boolean;
    handoffStatus?: HandoffStatus | string | null;
    handoffError?: string;
    fhirStatus?: string;
    fhirFailureMessage?: string;
  },
  placeholderPrefix: string,
): CardTag {
  if (HANDOFF_ACTIVE.includes(item.handoffStatus ?? '')) return { label: 'registering…', color: CYAN };
  const failed = item.handoffStatus === 'failed';
  // Legacy approvals only gave the row a placeholder uuid; it never reached the platform.
  if (item.platformOnly || (item.uuid && !item.uuid.startsWith(placeholderPrefix))) {
    const problems = [
      item.fhirStatus === 'failed' ? fhirFailed(item.fhirFailureMessage) : '',
      failed ? (item.handoffError ? `Re-approval failed: ${item.handoffError}` : 'Re-approval failed') : '',
    ].filter(Boolean);
    return problems.length
      ? { label: 'in platform', color: AMBER, title: problems.join('\n') }
      : { label: 'in platform', color: GREEN };
  }
  if (failed) return withTitle({ label: 'registration failed', color: RED }, item.handoffError);
  return { label: 'draft', color: GREY };
}

const BUILD_COLORS: Record<string, string> = { pending: AMBER, building: CYAN, completed: GREEN, failed: RED };

/** `build · <status>` for a portal-built tool or workflow; null for one uploaded straight to the platform. */
export function buildTag(item: { status?: string; platformOnly?: boolean }): CardTag | null {
  if (item.platformOnly || !item.status) return null;
  return { label: `build · ${item.status}`, color: BUILD_COLORS[item.status] ?? GREY };
}

const TYPES = ['gui', 'script', 'notebook'];

/** A tool's label (GUI / Script / Notebook) or a workflow's type, in one vocabulary. */
export function typeTag(type?: string | null): CardTag | null {
  const t = (type ?? '').toLowerCase();
  return TYPES.includes(t) ? { label: t } : null;
}

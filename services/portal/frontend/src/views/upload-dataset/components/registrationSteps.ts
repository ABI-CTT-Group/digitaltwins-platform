/**
 * Where a registration continues: each hub's wizard has its own URL, `/catalogue/<hub>/new` for a new item
 * and `/catalogue/<hub>/<id>/register?step=<step>` for one that exists (the router's Register* and
 * Continue*Registration routes).
 */
import type { RouteLocationNamedRaw } from 'vue-router';

export type Hub = 'tools' | 'workflows' | 'measurements' | 'models';
/** Tools and workflows: annotation, build. Measurements and models: upload (resume), annotation. */
export type RegistrationStep = 'annotation' | 'build' | 'upload';

const HUB_ROUTES: Record<Hub, { hub: string; continue: string }> = {
  tools: { hub: 'UploadToolDataset', continue: 'ContinueToolRegistration' },
  workflows: { hub: 'UploadWorkflowDataset', continue: 'ContinueWorkflowRegistration' },
  measurements: { hub: 'UploadMeasurementsDataset', continue: 'ContinueMeasurementRegistration' },
  models: { hub: 'UploadModelDataset', continue: 'ContinueModelRegistration' },
};

/** The step a tool's or workflow's Continue registration opens. The FHIR annotation is optional, so one that
 *  already has an annotation (or a build) goes on to its build. Measurements and models need no guess:
 *  Resume upload opens `upload`, Add/Edit FHIR annotation opens `annotation`. */
export function nextStep(row: { latestBuildId?: string; hasAnnotation?: boolean }): RegistrationStep {
  return row.latestBuildId || row.hasAnnotation ? 'build' : 'annotation';
}

export const registerRoute = (hub: Hub, id: string, step: RegistrationStep): RouteLocationNamedRaw =>
  ({ name: HUB_ROUTES[hub].continue, params: { id }, query: { step } });

export const hubRoute = (hub: Hub): RouteLocationNamedRaw => ({ name: HUB_ROUTES[hub].hub });

/**
 * Dashboard service — HTTP business interface for study/assay dashboard data.
 * Moved from bootstrap/dashboard_api.ts as part of the bootstrap ↔ services split.
 *
 * @see PLAN-frontend-refactoring-phase3.md § 阶段 6
 */
export {
  useDashboardProgrammes,
  useDashboardCategoryChildren,
  useDashboardWorkflows,
  useDashboardWorkflowDetail,
  useDashboardSeekAssay,
  useSaveAssayDetails,
  useDashboardGetAssayConfigDetails,
  useDashboardGetAssayLaunch,
  useDashboardGetDatasets,
  useDashboardSelectedDatasetSampleTypes,
} from '@/bootstrap/dashboard_api';

/**
 * Workflow service — HTTP business interface for workflow management.
 * Moved from bootstrap/workflow_api.ts as part of the bootstrap ↔ services split.
 *
 * @see PLAN-frontend-refactoring-phase3.md § 阶段 6
 */
export {
  useCheckToolName,
  useCreateWorkflow,
  useCreateWorkflowAnnotation,
  useWorkflowBuild,
  useDeleteWorkflow,
  useWorkflow,
  useWorkflowApproval,
} from '@/bootstrap/workflow_api';

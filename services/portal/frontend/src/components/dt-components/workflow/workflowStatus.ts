

export enum WorkflowStatus {
  PENDING = "pending",
  RUNNING = "running",
  SUCCEEDED = "succeeded",
  FAILED = "failed",
  CANCELLED = "cancelled",
}

export const WorkflowStatusMeta: Record<
  WorkflowStatus,
  { label: string;  color?: string; }
> = {
  [WorkflowStatus.PENDING]: {
    label: "Pending",
    color: "amber",
  },
  [WorkflowStatus.RUNNING]: {
    label: "Running",
    color: "blue",
  },
  [WorkflowStatus.SUCCEEDED]: {
    label: "Succeeded",
    color: "green",
  },
  [WorkflowStatus.FAILED]: {
    label: "Failed",
    color: "red",
  },
  [WorkflowStatus.CANCELLED]: {
    label: "Cancelled",
    color: "grey"
  }
};

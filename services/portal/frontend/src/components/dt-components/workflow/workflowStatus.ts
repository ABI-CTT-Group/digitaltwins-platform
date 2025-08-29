

export enum WorkflowStatus {
  PENDING = "pending",
  RUNNING = "running",
  SUCCEEDED = "succeeded",
  FAILED = "failed",
  CANCELED = "canceled",
}

export const WorkflowStatusMeta: Record<
  WorkflowStatus,
  { label: string;  bg?: string; text?: string; border?: string }
> = {
  [WorkflowStatus.PENDING]: {
    label: "Pending",
    bg: "#F5F5F5",
    text: "#616161",
    border: "#BDBDBD",
  },
  [WorkflowStatus.RUNNING]: {
    label: "Running",
    bg: "#E3F2FD",
    text: "#1565C0",
    border: "#90CAF9",
  },
  [WorkflowStatus.SUCCEEDED]: {
    label: "Succeeded",
    bg: "#E8F5E9",
    text: "#2E7D32",
    border: "#A5D6A7",
  },
  [WorkflowStatus.FAILED]: {
    label: "Failed",
    bg: "#FFEBEE",
    text: "#C62828",
    border: "#EF9A9A",
  },
  [WorkflowStatus.CANCELED]: {
    label: "Canceled",
    bg: "#FFF8E1",
    text: "#EF6C00",
    border: "#FFCC80",
  }
};

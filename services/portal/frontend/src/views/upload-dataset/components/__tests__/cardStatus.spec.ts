import { describe, expect, it } from "vitest";
import { datasetStatus, toolStatus, workflowStatus } from "../cardStatus";

// One case per row of the card state tables (docs/decisions/2026-11-06-card-status-sentence.md).
const TOOL = { id: "t1", name: "curator", label: "GUI", hasBackend: true, status: "completed", latestBuildId: "b1",
  createdAt: "", updatedAt: "" } as any;
const APPROVED = { ...TOOL, uuid: "a8d6da0e-1", handoffStatus: "completed" };
const pick = (s: ReturnType<typeof toolStatus>) => [s.sentence, s.tone, s.group, s.action];

describe("toolStatus", () => {
  it("not built yet: build it", () => {
    expect(pick(toolStatus({ ...TOOL, status: "pending", latestBuildId: undefined })))
      .toEqual(["Not built yet", "needs", "needs", "build"]);
  });

  it("building (or queued): its logs", () => {
    expect(pick(toolStatus({ ...TOOL, status: "building" }))).toEqual(["Building…", "running", "progress", "view-logs"]);
    expect(pick(toolStatus({ ...TOOL, status: "pending" }))).toEqual(["Building…", "running", "progress", "view-logs"]);
  });

  it("build failed: the reason, and its logs", () => {
    const s = toolStatus({ ...TOOL, status: "failed", buildError: "npm ERR! missing script" });
    expect(pick(s)).toEqual(["Build failed", "failed", "needs", "view-logs"]);
    expect(s.reason).toBe("npm ERR! missing script");
  });

  it("built, not in the platform: approve it", () => {
    const s = toolStatus(TOOL);
    expect(pick(s)).toEqual(["Built — not in the platform yet", "needs", "needs", "approve"]);
    expect(s.hint).toBe("Approve it so assays can use it.");
    // A legacy approval's placeholder never reached the platform.
    expect(toolStatus({ ...TOOL, uuid: "sparc-tool-$x" }).sentence).toBe("Built — not in the platform yet");
  });

  it("approving: no action while it runs", () => {
    for (const handoffStatus of ["uploading", "committing"]) {
      expect(pick(toolStatus({ ...TOOL, handoffStatus }))).toEqual(["Approving…", "running", "progress", undefined]);
    }
  });

  it("approval waiting for sign-in needs you", () => {
    expect(pick(toolStatus({ ...TOOL, handoffStatus: "awaiting_reauth" })))
      .toEqual(["Approving… waiting for you to sign in again", "needs", "needs", undefined]);
  });

  it("approval failed: the reason, approve again", () => {
    const s = toolStatus({ ...TOOL, handoffStatus: "failed", handoffError: "SEEK 403" });
    expect(pick(s)).toEqual(["Approval failed", "failed", "needs", "approve-again"]);
    expect(s.reason).toBe("SEEK 403");
  });

  it("in the platform: launch a GUI tool, nothing for a script", () => {
    expect(pick(toolStatus(APPROVED))).toEqual(["In the platform", "steady", "platform", "launch"]);
    expect(pick(toolStatus({ ...APPROVED, label: "Script" }))).toEqual(["In the platform", "steady", "platform", undefined]);
    expect(toolStatus(APPROVED).problems).toEqual([]);
  });

  it("in the platform with a newer build not approved: approve it", () => {
    expect(pick(toolStatus({ ...APPROVED, handoffStatus: null })))
      .toEqual(["In the platform — a newer build isn't approved yet", "needs", "needs", "approve"]);
  });

  it("in the platform, re-approval failed: a coral chip, approve again", () => {
    const s = toolStatus({ ...APPROVED, handoffStatus: "failed", handoffError: "MinIO 503" });
    expect(pick(s)).toEqual(["In the platform", "steady", "needs", "approve-again"]);
    expect(s.problems).toEqual([{ label: "re-approval failed", reason: "MinIO 503" }]);
  });

  it("in the platform, FHIR failed: retry FHIR", () => {
    const s = toolStatus({ ...APPROVED, fhirStatus: "failed", fhirFailureMessage: "HAPI 500" });
    expect(pick(s)).toEqual(["In the platform — FHIR publishing failed", "failed", "needs", "retry-fhir"]);
    expect(s.reason).toBe("HAPI 500");
  });

  it("GUI backend failed: a coral chip, Launch retries", () => {
    const s = toolStatus({ ...APPROVED, deployStatus: "failed", deployError: "port 8000 is already allocated" });
    expect(pick(s)).toEqual(["In the platform", "steady", "needs", "launch"]);
    expect(s.problems).toEqual([{ label: "backend failed", reason: "port 8000 is already allocated" }]);
  });

  it("in the platform while a rebuild runs or after it failed", () => {
    expect(pick(toolStatus({ ...APPROVED, status: "building" })))
      .toEqual(["In the platform — rebuilding…", "running", "progress", "view-logs"]);
    const failed = toolStatus({ ...APPROVED, status: "failed", buildError: "exit 1" });
    expect(pick(failed)).toEqual(["In the platform", "steady", "needs", "launch"]);
    expect(failed.problems).toEqual([{ label: "rebuild failed", reason: "exit 1" }]);
  });

  it("uploaded via the API: in the platform, no action", () => {
    const s = toolStatus({ ...TOOL, uuid: "t-9", platformOnly: true, latestBuildId: undefined, label: "Script" });
    expect(pick(s)).toEqual(["In the platform", "steady", "platform", undefined]);
    expect(toolStatus({ ...TOOL, uuid: "t-9", platformOnly: true, latestBuildId: undefined }).action).toBeUndefined();
  });

  it("a gui workflow's tool: approved through its workflow", () => {
    const wfTool = { ...TOOL, kind: "workflow", workflowName: "workflow_volview" };
    const s = toolStatus(wfTool);
    expect(pick(s)).toEqual(["Built — not in the platform yet", "needs", "needs", undefined]);
    expect(s.hint).toBe("Approve workflow_volview in Workflows to add it to the platform.");
    expect(pick(toolStatus({ ...wfTool, uuid: "tool-v" }))).toEqual(["In the platform", "steady", "platform", "launch"]);
  });
});

const WORKFLOW = { id: "w1", name: "seg", workflowType: "script", isSds: true, status: "completed", latestBuildId: "b1",
  createdAt: "", updatedAt: "" } as any;
const IN_PLATFORM = { ...WORKFLOW, uuid: "wf-1", handoffStatus: "completed", dagStatus: "deployed" };

describe("workflowStatus", () => {
  it("not built yet: no action until its wizard can be reopened", () => {
    expect(pick(workflowStatus({ ...WORKFLOW, status: "pending", latestBuildId: undefined })))
      .toEqual(["Not built yet", "needs", "needs", undefined]);
  });

  it("building, build failed", () => {
    expect(pick(workflowStatus({ ...WORKFLOW, status: "building" }))).toEqual(["Building…", "running", "progress", undefined]);
    const failed = workflowStatus({ ...WORKFLOW, status: "failed", buildError: "cwltool: invalid" });
    expect(pick(failed)).toEqual(["Build failed", "failed", "needs", undefined]);
    expect(failed.reason).toBe("cwltool: invalid");
  });

  it("built SDS workflow: approve it; failed approval: approve again", () => {
    expect(pick(workflowStatus(WORKFLOW))).toEqual(["Built — not in the platform yet", "needs", "needs", "approve"]);
    expect(pick(workflowStatus({ ...WORKFLOW, handoffStatus: "failed", handoffError: "x" })))
      .toEqual(["Approval failed", "failed", "needs", "approve-again"]);
    expect(pick(workflowStatus({ ...WORKFLOW, handoffStatus: "committing" }))).toEqual(["Approving…", "running", "progress", undefined]);
  });

  it("a legacy workflow that isn't an SDS package: not supported yet", () => {
    for (const legacy of [{ ...WORKFLOW, isSds: false }, { ...WORKFLOW, isSds: null, workflowType: undefined }]) {
      expect(pick(workflowStatus(legacy))).toEqual(["Not an SDS package — not supported yet", "steady", "other", undefined]);
    }
  });

  it("in the platform; an admin deploys a script workflow's DAG", () => {
    expect(pick(workflowStatus(IN_PLATFORM))).toEqual(["In the platform", "steady", "platform", undefined]);
    const notDeployed = { ...IN_PLATFORM, dagStatus: null };
    expect(workflowStatus(notDeployed).action).toBeUndefined();
    expect(pick(workflowStatus(notDeployed, { canDeploy: true }))).toEqual(["In the platform", "steady", "platform", "deploy-dag"]);
    expect(workflowStatus({ ...notDeployed, workflowType: "gui" }, { canDeploy: true }).action).toBeUndefined();
  });

  it("a DAG deploy running or failed", () => {
    expect(pick(workflowStatus({ ...IN_PLATFORM, dagStatus: "deploying" }, { canDeploy: true })))
      .toEqual(["In the platform — deploying the DAG…", "running", "progress", undefined]);
    const failed = workflowStatus({ ...IN_PLATFORM, dagStatus: "failed", dagError: "ImportError" }, { canDeploy: true });
    expect(pick(failed)).toEqual(["In the platform", "steady", "needs", "deploy-dag"]);
    expect(failed.problems).toEqual([{ label: "DAG deploy failed", reason: "ImportError" }]);
  });

  it("in the platform with a newer build, a failed re-approval, or FHIR failed", () => {
    expect(pick(workflowStatus({ ...IN_PLATFORM, handoffStatus: null })))
      .toEqual(["In the platform — a newer build isn't approved yet", "needs", "needs", "approve"]);
    expect(workflowStatus({ ...IN_PLATFORM, handoffStatus: "failed", handoffError: "e" }).problems)
      .toEqual([{ label: "re-approval failed", reason: "e" }]);
    expect(pick(workflowStatus({ ...IN_PLATFORM, fhirStatus: "failed" })))
      .toEqual(["In the platform — FHIR publishing failed", "failed", "needs", "retry-fhir"]);
  });

  it("uploaded via the API: in the platform", () => {
    const uploaded = { id: "wf-9", uuid: "wf-9", name: "u", platformOnly: true, status: "completed", workflowType: "gui" } as any;
    expect(pick(workflowStatus(uploaded))).toEqual(["In the platform", "steady", "platform", undefined]);
  });
});

const dataset = (status: string, extra: object = {}) => ({ id: "upload:m1", name: "m1", status, createdAt: "", updatedAt: "", ...extra }) as any;

describe("datasetStatus", () => {
  it("upload paused: resume it", () => {
    expect(pick(datasetStatus(dataset("pending_upload")))).toEqual(["Upload paused", "needs", "needs", "resume-upload"]);
  });

  it("staged: ready to approve, with or without an annotation", () => {
    expect(pick(datasetStatus(dataset("pending")))).toEqual(["Ready to approve", "needs", "needs", "approve"]);
    expect(pick(datasetStatus(dataset("pending", { hasAnnotation: true })))).toEqual(["Ready to approve", "needs", "needs", "approve"]);
  });

  it("approving", () => {
    expect(pick(datasetStatus(dataset("uploading")))).toEqual(["Approving…", "running", "progress", undefined]);
  });

  it("approval failed: the reason, approve again", () => {
    const s = datasetStatus(dataset("submit_failed", { failureMessage: "disk full" }));
    expect(pick(s)).toEqual(["Approval failed", "failed", "needs", "approve-again"]);
    expect(s.reason).toBe("disk full");
  });

  it("in the platform, or publishing to FHIR", () => {
    expect(pick(datasetStatus(dataset("completed", { uuid: "d1" })))).toEqual(["In the platform", "steady", "platform", undefined]);
    expect(pick(datasetStatus(dataset("uploading", { uuid: "d1" }))))
      .toEqual(["In the platform — publishing to FHIR…", "running", "progress", undefined]);
  });

  it("in the platform, FHIR failed: retry FHIR", () => {
    const s = datasetStatus(dataset("fhir_failed", { uuid: "d1", failureMessage: "HAPI 500" }));
    expect(pick(s)).toEqual(["In the platform — FHIR publishing failed", "failed", "needs", "retry-fhir"]);
    expect(s.reason).toBe("HAPI 500");
  });
});

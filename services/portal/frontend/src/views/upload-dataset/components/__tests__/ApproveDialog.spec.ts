import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

const adapter = vi.hoisted(() => ({ needsProject: true, start: vi.fn(), poll: vi.fn() }));
const projects = vi.hoisted(() => vi.fn());
vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/tool_api", () => ({ useSeekProjects: projects }));
vi.mock("../approveAdapters", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../approveAdapters")>()),
  approveAdapter: () => adapter,
}));

import ApproveDialog from "../ApproveDialog.vue";

let w: ReturnType<typeof mount> | undefined;
async function open(category: string, item: object) {
  w = mount(ApproveDialog, { props: { modelValue: false, category, item } as any,
    global: { plugins: [testVuetify()] }, attachTo: document.body });
  await w.setProps({ modelValue: true });
  await flushPromises();
}
const text = () => document.body.textContent ?? "";
const button = (label: string) =>
  Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find((b) => b.textContent?.trim() === label)!;

beforeEach(() => {
  vi.useFakeTimers();
  adapter.needsProject = true;
  projects.mockResolvedValue([{ id: 11, title: "Lesions" }]);
  adapter.start.mockResolvedValue({ state: "running", stage: "Uploading the build", percent: 25 });
});
afterEach(() => {
  w?.unmount();
  document.body.innerHTML = "";
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("ApproveDialog", () => {
  it("asks for a SEEK project for a tool, and hints when it has no annotation", async () => {
    await open("tools", { id: "t1", name: "curator", seekProjectId: 11, hasAnnotation: false });
    expect(text()).toContain("Approve curator?");
    expect(text()).toContain("SEEK project");
    expect(text()).toContain("No FHIR annotation, so nothing is published to FHIR.");
    expect(text()).not.toContain("Publish to FHIR");
  });

  it("asks nothing more for a measurement", async () => {
    adapter.needsProject = false;
    await open("measurements", { id: "upload:m1", name: "scans", hasAnnotation: true });
    expect(text()).not.toContain("SEEK project");
    expect(text()).not.toContain("No FHIR annotation");
    expect(projects).not.toHaveBeenCalled();
  });

  it("follows the approval to the end", async () => {
    await open("tools", { id: "t1", name: "curator", seekProjectId: 11 });
    button("Approve").click();
    await flushPromises();
    expect(adapter.start).toHaveBeenCalledWith(expect.objectContaining({ id: "t1" }), 11);
    expect(text()).toContain("Approving curator");
    expect(text()).toContain("Uploading the build");
    expect(text()).toContain("You can close this");

    adapter.poll.mockResolvedValue({ state: "done", stage: "In the platform" });
    await vi.advanceTimersByTimeAsync(2000);
    expect(text()).toContain("curator is in the platform.");
    expect(w!.emitted("finished")).toHaveLength(1);
  });

  it("says why an approval failed", async () => {
    await open("tools", { id: "t1", name: "curator", seekProjectId: 11 });
    button("Approve").click();
    await flushPromises();
    adapter.poll.mockResolvedValue({ state: "failed", stage: "Approval failed", error: "SEEK 403" });
    await vi.advanceTimersByTimeAsync(2000);
    expect(text()).toContain("Approval failed");
    expect(text()).toContain("SEEK 403");
  });

  it("says when a FHIR push failed after the item reached the platform", async () => {
    adapter.needsProject = false;
    adapter.start.mockResolvedValue({ state: "done", stage: "In the platform", fhirError: "HAPI 500" });
    await open("models", { id: "upload:m2", name: "segmenter" });
    button("Approve").click();
    await flushPromises();
    expect(text()).toContain("segmenter is in the platform.");
    expect(text()).toContain("FHIR publishing failed: HAPI 500. Retry it from the card.");
  });

  it("shows when it waits for you to sign in again", async () => {
    await open("workflows", { id: "w1", name: "seg", seekProjectId: 11 });
    button("Approve").click();
    await flushPromises();
    adapter.poll.mockResolvedValue({ state: "waiting", stage: "Waiting for you to sign in again" });
    await vi.advanceTimersByTimeAsync(2000);
    expect(text()).toContain("Waiting for you to sign in again");
  });

  it("closes mid-way without cancelling: the card keeps following it", async () => {
    await open("tools", { id: "t1", name: "curator", seekProjectId: 11 });
    button("Approve").click();
    await flushPromises();
    button("Close").click();
    await flushPromises();
    expect(w!.emitted("update:modelValue")?.at(-1)).toEqual([false]);
    expect(w!.emitted("finished")).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(6000);
    expect(adapter.poll).not.toHaveBeenCalled();
  });

  it("keeps the dialog open with the reason when the approval can't start", async () => {
    adapter.start.mockRejectedValue({ response: { status: 409, data: { detail: "No completed build to approve" } } });
    await open("tools", { id: "t1", name: "curator", seekProjectId: 11 });
    button("Approve").click();
    await flushPromises();
    expect(text()).toContain("Approval failed: No completed build to approve");
    expect(button("Approve")).toBeDefined();
  });

  it("waits for a SEEK project before approving a tool", async () => {
    await open("tools", { id: "t1", name: "curator" });
    expect(button("Approve").disabled).toBe(true);
  });
});

import { describe, expect, it, beforeEach, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/api_helpers", () => ({ useCheckName: vi.fn(async () => ({ available: true, message: "" })) }));
vi.mock("@/bootstrap/upload_source", () => ({ useUploadToolSource: vi.fn(), useUploadWorkflowSource: vi.fn() }));

const repo = vi.hoisted(() => ({ info: null as any }));
vi.mock("@/composables/useGithubRepoInfo", async () => {
  const { ref } = await import("vue");
  repo.info = ref({ foldersInRoot: [], isSds: false, cwlExists: false });
  return { useGitRepoInfo: () => ({ info: repo.info, refresh: vi.fn() }) };
});
vi.mock("@/composables/useLocalFolderInfo", async () => {
  const { ref } = await import("vue");
  return { useLocalFolderInfo: () => ({ info: ref({ foldersInRoot: [], isSds: false, cwlExists: false }), refresh: vi.fn() }) };
});

import BaseInformationStep from "../BaseInformationStep.vue";

// The source fields belong to CommonInfoForm; render only its slots, so the type radios are tested on their own.
const stubs = { CommonInfoForm: { template: "<div><slot name='dropzone' /><slot /></div>" }, LocalFolderDropzone: true };
const mountStep = (type: "tool" | "workflow") =>
  mount(BaseInformationStep, { props: { type }, global: { plugins: [testVuetify()], stubs } });
type Step = ReturnType<typeof mountStep>;
const typeGroup = (w: Step) => w.findAllComponents({ name: "VRadioGroup" })[0];
const labels = (w: Step) => typeGroup(w).findAllComponents({ name: "VRadio" }).map((r) => r.props("label"));
const pick = async (w: Step, value: string) => { typeGroup(w).vm.$emit("update:modelValue", value); await flushPromises(); };

async function submit(w: Step) {
  const vm = w.vm as any;
  vm.formData.name = "convert";
  vm.cwlCheck = true;  // the source check passed
  await w.findAll("button").find((b) => b.text().startsWith("Submit"))!.trigger("click");
  await flushPromises();
  return w.emitted("submit")?.[0]?.[0] as any;
}

describe("BaseInformationStep", () => {
  beforeEach(() => {
    repo.info.value = { foldersInRoot: [], isSds: false, cwlExists: false };
  });

  it("asks a workflow for its type before any source is chosen, defaulting to Script", () => {
    const w = mountStep("workflow");
    expect(w.text()).toContain("Choose the workflow type *");
    expect(labels(w)).toEqual(["Script", "Notebook", "Web GUI"]);
    expect(typeGroup(w).props("modelValue")).toBe("script");
  });

  it("sends the workflow type for any source", async () => {
    const w = mountStep("workflow");
    await pick(w, "notebook");
    expect(await submit(w)).toMatchObject({ workflowType: "notebook" });
  });

  it("lists tool types in the same order, defaulting to Script with no backend", () => {
    const w = mountStep("tool");
    expect(labels(w)).toEqual(["Script", "Notebook", "Web GUI"]);
    expect(typeGroup(w).props("modelValue")).toBe("Script");
    expect(w.text()).not.toContain("has backend?");
    expect((w.vm as any).formData.hasBackend).toBe(false);
  });

  it("asks about a backend only for a Web GUI tool, and never sends one for a Script tool", async () => {
    const w = mountStep("tool");
    await pick(w, "GUI");
    expect(w.text()).toContain("has backend?");
    expect((w.vm as any).formData.hasBackend).toBe(false);

    (w.vm as any).formData.hasBackend = true;
    await pick(w, "Script");
    expect(await submit(w)).toMatchObject({ label: "Script", hasBackend: false });
  });

  it("asks a gui SDS workflow how to build its tool, and sends it", async () => {
    repo.info.value = { foldersInRoot: ["backend", "frontend"], isSds: true, cwlExists: true };
    const w = mountStep("workflow");
    await pick(w, "gui");
    expect(w.text()).toContain("has backend?");

    Object.assign((w.vm as any).formData, { hasBackend: true, frontendFolder: "frontend", backendFolder: "backend" });
    expect(await submit(w)).toMatchObject({ workflowType: "gui", hasBackend: true, frontendFolder: "frontend",
      backendFolder: "backend", frontendBuildCommand: "npm run build:plugin" });
  });

  it("asks nothing more of a root-.cwl gui workflow", async () => {
    const w = mountStep("workflow");
    await pick(w, "gui");
    expect(w.text()).not.toContain("has backend?");
    expect(await submit(w)).not.toHaveProperty("hasBackend");
  });

  it("does not send a gui layout for another workflow type", async () => {
    repo.info.value = { foldersInRoot: ["frontend"], isSds: true, cwlExists: true };
    const w = mountStep("workflow");
    await pick(w, "script");
    expect(w.text()).not.toContain("has backend?");
    expect(await submit(w)).not.toHaveProperty("frontendBuildCommand");
  });
});

import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/api_helpers", () => ({ useCheckName: vi.fn(async () => ({ available: true, message: "" })) }));
vi.mock("@/bootstrap/upload_source", () => ({ useUploadToolSource: vi.fn(), useUploadWorkflowSource: vi.fn() }));
vi.mock("@/composables/useGithubRepoInfo", async () => {
  const { ref } = await import("vue");
  return { useGitRepoInfo: () => ({ info: ref({ foldersInRoot: [], isSds: false, cwlExists: false }), refresh: vi.fn() }) };
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
});

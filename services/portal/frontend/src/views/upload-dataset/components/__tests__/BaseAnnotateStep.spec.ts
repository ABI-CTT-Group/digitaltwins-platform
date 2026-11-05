import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
vi.mock("@/bootstrap/tool_api", () => ({
  useWorkflowTools: vi.fn(async () => []), useGetWorkflowToolAnnotation: vi.fn(), useGetToolLocalCwl: vi.fn(), useProbeToolSource: vi.fn(),
}));
vi.mock("@/views/upload-dataset/components/utils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/views/upload-dataset/components/utils")>()),
  getRepoRootCWLContent: vi.fn(),
}));
vi.mock("@/views/upload-dataset/components/workflow_cwls", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/views/upload-dataset/components/workflow_cwls")>()),
  loadWorkflowCwls: vi.fn(async () => { throw new Error("API rate limit exceeded"); }),
}));

import BaseAnnotateStep from "../BaseAnnotateStep.vue";
import { useGetToolLocalCwl } from "@/bootstrap/tool_api";
import { getRepoRootCWLContent } from "@/views/upload-dataset/components/utils";

const mountStep = (props: Record<string, unknown>) =>
  mount(BaseAnnotateStep, { props: props as any, global: { plugins: [testVuetify()] } });

describe("BaseAnnotateStep", () => {
  it("says why a workflow's CWL could not be read, before it is known to be an SDS package", async () => {
    const workflow = { id: "w1", sourceType: "github", repositoryUrl: "https://github.com/acme/convert" };
    const w = mount(BaseAnnotateStep, { props: { type: "workflow", data: workflow as any, submit: vi.fn() }, global: { plugins: [testVuetify()] } });
    await flushPromises();
    expect(w.text()).toContain("API rate limit exceeded");
  });

  it("shows and logs why a tool's CWL could not be parsed", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(useGetToolLocalCwl).mockResolvedValue({
      cwlFile: "tool_curator.cwl",
      content: "class: CommandLineTool\ninputs:\n  scan: File\n  scan: File\noutputs: {}\n",
    });

    const w = mountStep({ type: "tool", data: { id: "t1", sourceType: "local" } });
    await flushPromises();

    expect(w.text()).toContain("Failed to parse tool_curator.cwl: duplicated mapping key");
    expect(w.text()).not.toContain("No tool CWL file detected");
    expect(error).toHaveBeenCalledWith("Failed to load tool CWL", expect.any(Error));
    error.mockRestore();
  });

  it("logs why a workflow's CWL could not be read", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    mountStep({ type: "workflow", data: { id: "w1", sourceType: "github", repositoryUrl: "https://github.com/acme/convert" } });
    await flushPromises();

    expect(error).toHaveBeenCalledWith("Failed to load workflow CWL", expect.any(Error));
    error.mockRestore();
  });

  it("shows why a public GitHub tool's CWL could not be parsed", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(getRepoRootCWLContent).mockResolvedValue({
      cwlFile: "tool_curator.cwl", content: "inputs:\n  scan: File\n  scan: File\n",
    });

    const w = mountStep({ type: "tool", data: { id: "t1", sourceType: "github", repositoryUrl: "https://github.com/acme/curator" } });
    await flushPromises();

    expect(w.text()).toContain("Failed to parse tool_curator.cwl: duplicated mapping key");
    error.mockRestore();
  });

  it("shows why a public GitHub tool's CWL could not be fetched", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(getRepoRootCWLContent).mockRejectedValue(new Error("API rate limit exceeded"));

    const w = mountStep({ type: "tool", data: { id: "t1", sourceType: "github", repositoryUrl: "https://github.com/acme/curator" } });
    await flushPromises();

    expect(w.text()).toContain("API rate limit exceeded");
    error.mockRestore();
  });

  describe("is optional", () => {
    const CWL = { cwlFile: "tool_curator.cwl", content: "class: CommandLineTool\ninputs:\n  scan: File\noutputs: {}\n" };
    const button = (w: ReturnType<typeof mount>, label: string) => w.findAll("button").find((b) => b.text() === label)!;
    const mountTool = async (extra: Record<string, unknown> = {}) => {
      vi.mocked(useGetToolLocalCwl).mockResolvedValue(CWL);
      const w = mountStep({ type: "tool", data: { id: "t1", sourceType: "local" }, submit: vi.fn(async () => {}), ...extra });
      await flushPromises();
      return w;
    };
    const saved = (w: ReturnType<typeof mount>) => {
      const [id, note] = ((w.props() as any).submit as ReturnType<typeof vi.fn>).mock.calls[0];
      return { id, note: JSON.parse(note) };
    };

    it("skips without saving anything", async () => {
      const w = await mountTool();
      expect(w.text()).toContain("FHIR annotation (optional)");
      await button(w, "Skip for now").trigger("click");
      expect(w.emitted("skip")).toHaveLength(1);
      expect((w.props() as any).submit).not.toHaveBeenCalled();
    });

    it("saves the annotation as the item's FHIR note", async () => {
      const w = await mountTool();
      await button(w, "Save annotation").trigger("click");
      await flushPromises();
      expect(saved(w)).toEqual({ id: "t1", note: { name: "tool_curator", inputs: [{ name: "scan", resource: "" }], outputs: [] } });
    });

    it("fills in the saved annotation to edit it", async () => {
      const savedNote = JSON.stringify({ name: "tool_curator", inputs: [{ name: "scan", resource: "ImagingStudy" }], outputs: [] });
      const w = await mountTool({ savedNote });
      await button(w, "Save annotation").trigger("click");
      await flushPromises();
      expect(saved(w).note.inputs).toEqual([{ name: "scan", resource: "ImagingStudy" }]);
    });

    it("shows why saving failed, and stays on the step", async () => {
      const w = await mountTool({ submit: vi.fn().mockRejectedValue({ response: { status: 500, data: { detail: "database is locked" } } }) });
      await button(w, "Save annotation").trigger("click");
      await flushPromises();
      expect(w.text()).toContain("Saving the annotation failed: database is locked");
      expect(w.emitted("skip")).toBeUndefined();
    });
  });
});

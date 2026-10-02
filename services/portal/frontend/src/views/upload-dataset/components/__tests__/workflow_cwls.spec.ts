import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/bootstrap/http", () => ({ default: {}, dtApi: {} }));
const { getRepoContents, localCwl, probe } = vi.hoisted(() => ({ getRepoContents: vi.fn(), localCwl: vi.fn(), probe: vi.fn() }));
vi.mock("@/views/upload-dataset/components/utils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/views/upload-dataset/components/utils")>()), getRepoContents,
}));
vi.mock("@/bootstrap/workflow_api", () => ({ useGetWorkflowLocalCwl: localCwl, useProbeWorkflowSource: probe }));

import { loadWorkflowCwls } from "../workflow_cwls";

const WF = "class: Workflow\nsteps:\n  convert:\n    run: tool_convert.cwl\n";
const TOOL = "class: CommandLineTool\ninputs:\n  src: File\n";
const workflow = (sourceType: string) => ({ id: "w1", sourceType, repositoryUrl: "https://github.com/acme/convert" }) as any;
const file = (name: string) => ({ type: "file", name });
const encoded = (text: string) => ({ data: { content: btoa(text) } });

describe("loadWorkflowCwls", () => {
  beforeEach(() => vi.resetAllMocks());

  it("takes isSds from /cwl for a local source", async () => {
    localCwl.mockResolvedValue({ cwlFile: "workflow_convert.cwl", content: WF, isSds: true,
      toolCwls: [{ cwlFile: "tool_convert.cwl", content: TOOL }] });
    const res = await loadWorkflowCwls(workflow("local"));
    expect(res.isSds).toBe(true);
    expect(res.tools.map((t) => t.cwlFile)).toEqual(["tool_convert.cwl"]);
  });

  it("finds an SDS package on public GitHub by its dataset_description.xlsx, even with a root .cwl", async () => {
    getRepoContents.mockImplementation(async (_url: string, path = "") => {
      if (path === "") return { data: [file("dataset_description.xlsx"), file("legacy.cwl")] };
      if (path === "primary") return { data: [file("workflow_convert.cwl"), file("tool_convert.cwl")] };
      return encoded(path.endsWith("workflow_convert.cwl") ? WF : TOOL);
    });
    const res = await loadWorkflowCwls(workflow("github"));
    expect(res.isSds).toBe(true);
    expect(res.content.class).toBe("Workflow");
    expect(res.tools.map((t) => t.cwlFile)).toEqual(["tool_convert.cwl"]);
  });

  it("reads a root .cwl on public GitHub as not SDS", async () => {
    getRepoContents.mockImplementation(async (_url: string, path = "") =>
      path === "" ? { data: [file("flow.cwl"), file("README.md")] } : encoded(WF));
    const res = await loadWorkflowCwls(workflow("github"));
    expect(res).toMatchObject({ isSds: false, tools: [] });
    expect(getRepoContents).toHaveBeenCalledWith("https://github.com/acme/convert", "flow.cwl");
  });

  it("takes isSds from /probe-source for private GitHub and other hosts", async () => {
    probe.mockResolvedValue({ ok: true, data: { isSds: true, cwlContent: WF,
      toolCwls: [{ cwlFile: "tool_convert.cwl", content: TOOL }] } });
    const res = await loadWorkflowCwls(workflow("github"), { token: "<REDACTED>" });
    expect(res.isSds).toBe(true);
    expect(probe).toHaveBeenCalledWith(expect.objectContaining({ sourceType: "github", token: "<REDACTED>" }));
    expect(getRepoContents).not.toHaveBeenCalled();
  });
});

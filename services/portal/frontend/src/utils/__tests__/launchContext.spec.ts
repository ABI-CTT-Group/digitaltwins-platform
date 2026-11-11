import { describe, expect, it } from "vitest";
import type { AssayGuiContext, LaunchContext } from "@/models/types";
import exampleJson from "@/models/launch-context.example.json";
import { toLaunchContext } from "../launchContext";

// The example is the template GUI tool authors copy (docs/gui-tool-authoring.md); typing it here
// makes vue-tsc fail when it stops matching the contract.
const example: Omit<LaunchContext, "getAccessToken"> = exampleJson;

const ctx: AssayGuiContext = {
  ...example,
  tool: { name: "annotator", path: "/b/annotator.umd.js", expose: "annotator_1" },
};

const keysOf = (o: object) => Object.keys(o).sort();

describe("toLaunchContext", () => {
  it("hands the tool the assay's data and a token getter, but not the portal's own tool record", () => {
    const getAccessToken = () => "tok";
    const launch = toLaunchContext(ctx, getAccessToken);
    expect(launch).toEqual({ ...example, getAccessToken });
    expect(launch).not.toHaveProperty("tool");
    expect(launch.getAccessToken()).toBe("tok");
  });

  it("matches the example field for field, so the template documents every field", () => {
    const launch = toLaunchContext(ctx, () => "tok");
    expect(keysOf(launch)).toEqual(keysOf({ ...example, getAccessToken: null }));
    expect(keysOf(launch.inputs[0])).toEqual(keysOf(example.inputs[0]));
    expect(keysOf(launch.inputs[0].files[0])).toEqual(keysOf(example.inputs[0].files[0]));
  });
});

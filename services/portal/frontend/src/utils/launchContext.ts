import type { AssayGuiContext, LaunchContext } from "@/models/types";

/** The launch context /tool-view provides to a GUI tool: the assay's data, without the portal's tool record. */
export function toLaunchContext(ctx: AssayGuiContext, getAccessToken: LaunchContext["getAccessToken"]): LaunchContext {
  return {
    schemaVersion: ctx.schemaVersion,
    assayId: ctx.assayId,
    cohort: ctx.cohort,
    inputs: ctx.inputs,
    getAccessToken,
  };
}

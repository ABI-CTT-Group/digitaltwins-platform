import { describe, expect, it } from "vitest";
import { buildTag, deployTag, handoffRegistrationTag, measurementRegistrationTag, typeTag } from "../cardTags";

const GREY = "#9fb4bf", CYAN = "#5fd6e8", GREEN = "#6fd49a", RED = "#ff6b6b", AMBER = "#ffb74d";

describe("measurementRegistrationTag", () => {
  const tag = (status: string, extra: object = {}) => measurementRegistrationTag({ status, ...extra });

  it("names each session state", () => {
    expect(tag("pending_upload")).toEqual({ label: "upload paused", color: GREY });
    expect(tag("pending")).toEqual({ label: "draft", color: GREY });
    expect(tag("uploading")).toEqual({ label: "registering…", color: CYAN });
    expect(tag("submit_failed", { failureMessage: "disk full" }))
      .toEqual({ label: "registration failed", color: RED, title: "disk full" });
  });

  it("calls every committed dataset in platform, amber when FHIR failed", () => {
    expect(tag("completed", { uuid: "d1" })).toEqual({ label: "in platform", color: GREEN });
    // A FHIR push in flight: the files are already stored.
    expect(tag("uploading", { uuid: "d1" })).toEqual({ label: "in platform", color: GREEN });
    expect(tag("fhir_failed", { uuid: "d1", failureMessage: "HAPI 500" }))
      .toEqual({ label: "in platform", color: AMBER, title: "FHIR publishing failed: HAPI 500" });
    expect(tag("fhir_failed", { uuid: "d1" }).title).toBe("FHIR publishing failed");
  });
});

describe("handoffRegistrationTag", () => {
  const tag = (item: object) => handoffRegistrationTag(item, "sparc-tool-");

  it("is a draft until approved, including a legacy placeholder", () => {
    expect(tag({})).toEqual({ label: "draft", color: GREY });
    expect(tag({ uuid: "sparc-tool-$x" })).toEqual({ label: "draft", color: GREY });
  });

  it("is registering while any handoff step runs", () => {
    for (const handoffStatus of ["uploading", "awaiting_reauth", "committing"]) {
      expect(tag({ handoffStatus, uuid: "a1" })).toEqual({ label: "registering…", color: CYAN });
    }
  });

  it("reports a failed first approval with its error", () => {
    expect(tag({ handoffStatus: "failed", handoffError: "SEEK 403" }))
      .toEqual({ label: "registration failed", color: RED, title: "SEEK 403" });
  });

  it("is in platform once approved or uploaded through the API", () => {
    expect(tag({ uuid: "a1", handoffStatus: "completed" })).toEqual({ label: "in platform", color: GREEN });
    expect(tag({ uuid: "b1", platformOnly: true })).toEqual({ label: "in platform", color: GREEN });
    expect(tag({ uuid: "a1", fhirStatus: "pushing" })).toEqual({ label: "in platform", color: GREEN });
  });

  it("stays in platform but turns amber when FHIR or a re-approval failed", () => {
    expect(tag({ uuid: "a1", fhirStatus: "failed", fhirFailureMessage: "HAPI 500" }))
      .toEqual({ label: "in platform", color: AMBER, title: "FHIR publishing failed: HAPI 500" });
    expect(tag({ uuid: "a1", handoffStatus: "failed", handoffError: "SEEK 403" }))
      .toEqual({ label: "in platform", color: AMBER, title: "Re-approval failed: SEEK 403" });
    expect(tag({ uuid: "a1", handoffStatus: "failed", fhirStatus: "failed" }).title)
      .toBe("FHIR publishing failed\nRe-approval failed");
  });

  it("uses the given placeholder prefix", () => {
    expect(handoffRegistrationTag({ uuid: "sparc-workflow-$x" }, "sparc-workflow-").label).toBe("draft");
    expect(handoffRegistrationTag({ uuid: "sparc-workflow-$x" }, "sparc-tool-").label).toBe("in platform");
  });
});

describe("buildTag", () => {
  it("prefixes the raw build status", () => {
    expect(buildTag({ status: "pending" })).toEqual({ label: "build · pending", color: AMBER });
    expect(buildTag({ status: "building" })).toEqual({ label: "build · building", color: CYAN });
    expect(buildTag({ status: "completed" })).toEqual({ label: "build · completed", color: GREEN });
    expect(buildTag({ status: "failed" })).toEqual({ label: "build · failed", color: RED });
  });

  it("is absent for an item the portal never built", () => {
    expect(buildTag({ status: "completed", platformOnly: true })).toBeNull();
    expect(buildTag({ status: "" })).toBeNull();
  });
});

describe("deployTag", () => {
  it("prefixes a script workflow's DAG deploy status", () => {
    expect(deployTag("pending")).toEqual({ label: "deploy · pending", color: GREY });
    expect(deployTag("deploying")).toEqual({ label: "deploy · deploying", color: CYAN });
    expect(deployTag("deployed")).toEqual({ label: "deploy · deployed", color: GREEN });
  });

  it("explains a failed deploy on hover", () => {
    expect(deployTag("failed", "dag_id must be Path(__file__).parent.name"))
      .toEqual({ label: "deploy · failed", color: RED, title: "dag_id must be Path(__file__).parent.name" });
    expect(deployTag("failed", null)).toEqual({ label: "deploy · failed", color: RED });
  });

  it("is absent for a workflow without a DAG", () => {
    expect(deployTag(undefined)).toBeNull();
    expect(deployTag(null)).toBeNull();
  });
});

describe("typeTag", () => {
  it("names tool labels and workflow types with one vocabulary", () => {
    for (const [type, label] of [["GUI", "gui"], ["Script", "script"], ["Notebook", "notebook"],
      ["gui", "gui"], ["script", "script"], ["notebook", "notebook"]]) {
      expect(typeTag(type)).toEqual({ label });
    }
  });

  it("is absent for an unknown or missing type", () => {
    expect(typeTag(undefined)).toBeNull();
    expect(typeTag("")).toBeNull();
    expect(typeTag("cwl")).toBeNull();
  });
});

import { describe, expect, it } from "vitest";
import { nextStep, registerRoute } from "../registrationSteps";

describe("nextStep", () => {
  it("opens a tool or workflow at its FHIR annotation until it has one, then at its build", () => {
    expect(nextStep({ latestBuildId: undefined, hasAnnotation: false })).toBe("annotation");
    expect(nextStep({ latestBuildId: undefined, hasAnnotation: true })).toBe("build");
    expect(nextStep({ latestBuildId: "b1", hasAnnotation: false })).toBe("build");
  });
});

describe("registerRoute", () => {
  it("names each hub's wizard for an existing item", () => {
    expect(registerRoute("tools", "t1", "build"))
      .toEqual({ name: "ContinueToolRegistration", params: { id: "t1" }, query: { step: "build" } });
    expect(registerRoute("workflows", "w1", "annotation").name).toBe("ContinueWorkflowRegistration");
    expect(registerRoute("measurements", "upload:m1", "upload").name).toBe("ContinueMeasurementRegistration");
    expect(registerRoute("models", "upload:m2", "annotation").name).toBe("ContinueModelRegistration");
  });
});

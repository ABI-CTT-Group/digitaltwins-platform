import { describe, expect, it } from "vitest";
import { describeApiError } from "../apiError";

describe("describeApiError", () => {
  it("says what the server said", () => {
    expect(describeApiError({ response: { status: 400, data: { detail: "Plugin with this name already exists" } } }, "Saving"))
      .toBe("Saving failed: Plugin with this name already exists");
  });

  it("falls back to the status when the server gave no reason", () => {
    expect(describeApiError({ response: { status: 403, data: {} } }, "Saving")).toBe("Saving failed: you don't have permission.");
    expect(describeApiError({ isAxiosError: true, message: "Network Error" }, "Saving"))
      .toBe("Saving failed: network error, please check your connection.");
  });

  it("uses a thrown error's message", () => {
    expect(describeApiError(new Error("No CWL file found"), "Building")).toBe("Building failed: No CWL file found");
  });
});

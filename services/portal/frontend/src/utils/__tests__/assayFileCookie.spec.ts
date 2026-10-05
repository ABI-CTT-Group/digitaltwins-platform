import { describe, expect, it } from "vitest";

import { assayFileCookie, clearAssayFileCookie } from "../assayFileCookie";

// VolView fetches `urls=` with the browser's plain fetch, which carries no Authorization header
// but does send same-origin cookies. The token therefore rides in a cookie scoped to the one
// path that needs it: the assay's input-files proxy.
describe("assayFileCookie", () => {
  it("scopes the token to the assay's input-files path for the token's lifetime", () => {
    expect(assayFileCookie("43", "jwt", "http:")).toBe(
      "dt_assay_file_token=jwt; path=/api/dashboard/assays/43/input-files; max-age=300; samesite=strict",
    );
  });

  it("marks the cookie secure on https", () => {
    expect(assayFileCookie("43", "jwt", "https:")).toContain("; secure");
  });

  it("expires the cookie on the same path when clearing", () => {
    expect(clearAssayFileCookie("43")).toBe(
      "dt_assay_file_token=; path=/api/dashboard/assays/43/input-files; max-age=0; samesite=strict",
    );
  });
});

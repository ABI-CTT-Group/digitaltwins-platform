// @vitest-environment node
// The Dockerfile runs `yarn install --frozen-lockfile` and then `COPY . .`. Without these
// .dockerignore entries, a developer's local node_modules (or a stale build/) overwrites the clean
// install, and the image bundles whatever versions happen to be on that host instead of yarn.lock.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const dockerignore = fileURLToPath(new URL("../../.dockerignore", import.meta.url));

describe(".dockerignore", () => {
  it.each(["node_modules", "build"])("keeps the local %s out of the image build context", (entry) => {
    const lines = readFileSync(dockerignore, "utf8")
      .split("\n")
      .map((l) => l.trim().replace(/^\/|\/$/g, ""));
    expect(lines).toContain(entry);
  });
});

import { describe, expect, it } from "vitest";
import { chooseView, viewsFor } from "../dashboardView";

const roles = (r: Partial<Record<"admin" | "researcher" | "clinician", boolean>>) =>
  ({ admin: false, researcher: false, clinician: false, ...r });

describe("viewsFor", () => {
  it("gives an admin both views, clinician first", () => {
    expect(viewsFor(roles({ admin: true }))).toEqual(["clinician", "researcher"]);
  });

  it("gives a researcher and a clinician one view each", () => {
    expect(viewsFor(roles({ researcher: true }))).toEqual(["researcher"]);
    expect(viewsFor(roles({ clinician: true }))).toEqual(["clinician"]);
  });

  it("gives someone with both roles both views", () => {
    expect(viewsFor(roles({ researcher: true, clinician: true }))).toEqual(["clinician", "researcher"]);
  });

  it("gives no view to someone with neither role", () => {
    expect(viewsFor(roles({}))).toEqual([]);
  });
});

describe("chooseView", () => {
  const both = ["clinician", "researcher"] as const;

  it("opens the view the URL asks for", () => {
    expect(chooseView([...both], { asked: "clinician", hasTrail: true, stored: "researcher" })).toBe("clinician");
  });

  it("ignores a view the user can't see", () => {
    expect(chooseView(["researcher"], { asked: "clinician", hasTrail: false, stored: null })).toBe("researcher");
    expect(chooseView([...both], { asked: "nonsense", hasTrail: false, stored: null })).toBe("researcher");
  });

  it("opens the researcher view for a drill-down trail", () => {
    expect(chooseView([...both], { asked: null, hasTrail: true, stored: "clinician" })).toBe("researcher");
  });

  it("opens the view last chosen in this browser", () => {
    expect(chooseView([...both], { asked: null, hasTrail: false, stored: "clinician" })).toBe("clinician");
  });

  it("starts in the researcher view", () => {
    expect(chooseView([...both], { asked: null, hasTrail: false, stored: null })).toBe("researcher");
  });

  it("always gives a clinician the clinician view", () => {
    expect(chooseView(["clinician"], { asked: "researcher", hasTrail: true, stored: "researcher" })).toBe("clinician");
  });
});

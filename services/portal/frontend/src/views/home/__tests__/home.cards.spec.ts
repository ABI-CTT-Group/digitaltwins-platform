import { describe, expect, it } from "vitest";
import { cards } from "../home.cards";

describe("home cards", () => {
  it("has one study dashboard card, for admins, researchers and clinicians", () => {
    const dashboards = cards.filter(c => /study dashboard/i.test(c.title));
    expect(dashboards).toHaveLength(1);
    expect(dashboards[0]).toMatchObject({
      title: "Study dashboard",
      description: "Enables clinicians to collaborate with researchers to assess efficacy of AI/digital twin driven workflows.",
      requireRoles: ["admin", "researcher", "clinician"],
      action: { type: "route", name: "StudyDashboardPrototype" },
    });
  });

  it("has no separate clinician dashboard card", () => {
    expect(cards.some(c => /clinician dashboard/i.test(c.title))).toBe(false);
    expect(cards.some(c => c.action?.type === "route" && c.action.name === "ClinicianDashboard")).toBe(false);
  });

  it("never says prototype", () => {
    for (const c of cards) expect(`${c.title} ${c.description}`).not.toMatch(/prototype/i);
  });
});

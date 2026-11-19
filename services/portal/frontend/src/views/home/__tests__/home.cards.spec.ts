import { describe, expect, it } from "vitest";
import { cards } from "../home.cards";

describe("home cards", () => {
  it("puts the Study dashboard (prototype) right after the real study dashboard, for admins only", () => {
    const at = cards.findIndex(c => c.title === "Study dashboard");
    const proto = cards[at + 1];
    expect(proto).toMatchObject({
      title: "Study dashboard (prototype)",
      requireRoles: ["admin"],
      action: { type: "route", name: "StudyDashboardPrototype" },
    });
    expect(proto.image).toBe(cards[at].image);
  });

  it("keeps the real study dashboard card on the real dashboard", () => {
    expect(cards.find(c => c.title === "Study dashboard")?.action).toEqual({ type: "route", name: "StudyDashboard" });
  });
});

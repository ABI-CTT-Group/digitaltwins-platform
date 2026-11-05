import { describe, expect, it } from "vitest";
import { filterCounts, hubFilterFn, needsFirst } from "../hubFilter";
import type { CardStatus } from "../cardStatus";

const status = (group: CardStatus["group"]): CardStatus => ({ sentence: group, tone: "steady", group, problems: [] });
const ITEMS = [
  { id: "a", group: "platform" }, { id: "b", group: "needs" }, { id: "c", group: "progress" },
  { id: "d", group: "other" }, { id: "e", group: "needs" },
] as const;
const statusOf = (item: { group: CardStatus["group"] }) => status(item.group);

describe("hub filter", () => {
  it("All shows everything; each group shows its own", () => {
    const ids = (f: Parameters<typeof hubFilterFn>[0]) => {
      const fn = hubFilterFn(f, statusOf);
      return fn ? ITEMS.filter(fn).map((i) => i.id) : ITEMS.map((i) => i.id);
    };
    expect(ids("all")).toEqual(["a", "b", "c", "d", "e"]);
    expect(hubFilterFn("all", statusOf)).toBeUndefined();
    expect(ids("needs")).toEqual(["b", "e"]);
    expect(ids("progress")).toEqual(["c"]);
    expect(ids("platform")).toEqual(["a"]);
  });

  it("counts each group", () => {
    expect(filterCounts([...ITEMS], statusOf)).toEqual({ all: 5, needs: 2, progress: 1, platform: 1 });
  });

  it("sorts what needs you first and keeps the rest in order", () => {
    expect([...ITEMS].sort(needsFirst(statusOf)).map((i) => i.id)).toEqual(["b", "e", "a", "c", "d"]);
  });
});

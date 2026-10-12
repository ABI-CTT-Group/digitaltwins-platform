import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formatDate } from "../utils";

const NOW = new Date("2026-10-12T01:54:32Z");
const ago = (ms: number) => new Date(NOW.getTime() - ms).toISOString();
const SEC = 1000, MIN = 60 * SEC, HOUR = 60 * MIN, DAY = 24 * HOUR;

describe("formatDate", () => {
  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(NOW); });
  afterEach(() => vi.useRealTimers());

  it("says just now under a minute", () => {
    expect(formatDate(ago(0))).toBe("just now");
    expect(formatDate(ago(59 * SEC))).toBe("just now");
    // The API's own format: a dataset created 86 s before the clock reading.
    expect(formatDate("2026-10-12T01:53:06.965345+00:00")).toBe("1 minute ago");
  });

  it("counts minutes and hours within a day", () => {
    expect(formatDate(ago(MIN))).toBe("1 minute ago");
    expect(formatDate(ago(59 * MIN))).toBe("59 minutes ago");
    expect(formatDate(ago(HOUR))).toBe("1 hour ago");
    expect(formatDate(ago(23 * HOUR + 59 * MIN))).toBe("23 hours ago");
  });

  it("counts whole days, months and years, rounding down", () => {
    expect(formatDate(ago(DAY))).toBe("1 day ago");
    expect(formatDate(ago(30 * HOUR))).toBe("1 day ago");
    expect(formatDate(ago(29 * DAY))).toBe("29 days ago");
    expect(formatDate(ago(30 * DAY))).toBe("1 month ago");
    expect(formatDate(ago(300 * DAY))).toBe("10 months ago");
    expect(formatDate(ago(365 * DAY))).toBe("1 year ago");
    expect(formatDate(ago(800 * DAY))).toBe("2 years ago");
  });

  it("treats a timestamp slightly in the future (clock skew) as just now", () => {
    expect(formatDate(new Date(NOW.getTime() + 5 * SEC).toISOString())).toBe("just now");
  });
});

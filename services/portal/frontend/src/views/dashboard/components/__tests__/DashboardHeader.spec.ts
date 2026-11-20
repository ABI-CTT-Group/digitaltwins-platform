import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";
import DashboardHeader from "../DashboardHeader.vue";

const mountHeader = (currentCategory: string, count = 5) =>
  mount(DashboardHeader, {
    props: { rootLabel: "Study dashboard", breadcrumbs: [], currentCategory, count, loading: false },
    global: { plugins: [testVuetify()] },
  });

describe("DashboardHeader title", () => {
  it("calls the assay level the study design, and still counts assays", () => {
    const w = mountHeader("Assays");
    expect(w.find("h1").text()).toBe("Assays (study design)");
    expect(w.find(".dash-header__count").text()).toBe("5 assays");
  });

  it("shows other levels by their category", () => {
    const w = mountHeader("Studies", 2);
    expect(w.find("h1").text()).toBe("Studies");
    expect(w.find(".dash-header__count").text()).toBe("2 studies");
  });
});

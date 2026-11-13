import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { flushPromises, mount, RouterLinkStub, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { testVuetify } from "@/testing/vuetify";
import { useWorklistStore } from "../worklistStore";

import StudyListView from "../StudyListView.vue";

let wrapper: VueWrapper | undefined;
afterEach(() => wrapper?.unmount());
beforeEach(() => {
  localStorage.clear();
  setActivePinia(createPinia());
});

async function render() {
  wrapper = mount(StudyListView, { global: { plugins: [testVuetify()], stubs: { RouterLink: RouterLinkStub } } });
  await flushPromises();
  return wrapper;
}

const rows = (w: VueWrapper) => w.findAll("[data-test=study-row]");

describe("StudyListView", () => {
  it("lists the one example study with its progress", async () => {
    const w = await render();
    expect(rows(w)).toHaveLength(1);
    const row = rows(w)[0];
    expect(row.find("h2").text()).toBe("Breast MRI reading");
    expect(row.find("[data-test=study-reviewed]").text()).toBe("15 of 36 reviewed");
    expect(row.find("[data-test=study-left]").text()).toBe("21 to review");
    expect(row.find("progress").attributes()).toMatchObject({ value: "15", max: "36" });
  });

  it("opens the study's worklist from its row", async () => {
    const w = await render();
    expect(w.findComponent(RouterLinkStub).props("to")).toEqual({
      name: "ClinicianStudyWorklist",
      params: { studyId: "breast-mri-reading" },
    });
  });

  it("shows decisions made on the worklist", async () => {
    const w = await render();
    useWorklistStore().decide("sub-013", "confirmed", null, "Dr A. Reader");
    await flushPromises();
    expect(rows(w)[0].find("[data-test=study-reviewed]").text()).toBe("16 of 36 reviewed");
    expect(rows(w)[0].find("[data-test=study-left]").text()).toBe("20 to review");
  });
});

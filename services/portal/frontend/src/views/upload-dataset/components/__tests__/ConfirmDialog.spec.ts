import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { testVuetify } from "@/testing/vuetify";

import ConfirmDialog from "../ConfirmDialog.vue";

const mountDialog = (action: () => Promise<unknown>) => mount(ConfirmDialog, {
  props: { modelValue: true, title: "Delete VolView?", text: "It's removed from the portal.", confirmLabel: "Delete tool", action },
  global: { plugins: [testVuetify()] },
  attachTo: document.body,
});
const button = (label: string) =>
  Array.from(document.querySelectorAll("button")).find((b) => b.textContent?.includes(label)) as HTMLButtonElement;

// Every delete and cancel-upload on the hubs asks first, then runs the hub's call.
describe("ConfirmDialog", () => {
  it("runs the action on confirm and closes", async () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const w = mountDialog(action);
    await flushPromises();
    expect(document.body.textContent).toContain("Delete VolView?");
    button("Delete tool").click();
    await flushPromises();
    expect(action).toHaveBeenCalledOnce();
    expect(w.emitted("update:modelValue")?.at(-1)).toEqual([false]);
    w.unmount();
  });

  it("keeps the dialog open with the reason when the action fails", async () => {
    const w = mountDialog(() => Promise.reject({ response: { status: 409, data: { detail: "Used by workflow_volview" } } }));
    await flushPromises();
    button("Delete tool").click();
    await flushPromises();
    expect(document.body.textContent).toContain("Used by workflow_volview");
    expect(w.emitted("update:modelValue")).toBeUndefined();
    w.unmount();
  });

  it("cancels without running the action", async () => {
    const action = vi.fn();
    const w = mountDialog(action);
    await flushPromises();
    button("Cancel").click();
    await flushPromises();
    expect(action).not.toHaveBeenCalled();
    expect(w.emitted("update:modelValue")?.at(-1)).toEqual([false]);
    w.unmount();
  });
});

// jsdom lacks ResizeObserver and visualViewport, which Vuetify's overlays (v-dialog, menus) use.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

if (!globalThis.visualViewport) {
  Object.defineProperty(globalThis, "visualViewport", {
    value: Object.assign(new EventTarget(), { width: 1024, height: 768, offsetLeft: 0, offsetTop: 0, scale: 1 }),
  });
}

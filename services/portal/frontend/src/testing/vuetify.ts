import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";

/** A Vuetify instance for mounting components in tests: `mount(C, { global: { plugins: [testVuetify()] } })`. */
export const testVuetify = () => createVuetify({ components, directives });

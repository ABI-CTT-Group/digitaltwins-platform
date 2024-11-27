/**
 * plugins/index.ts
 *
 * Automatically included in `./src/main.ts`
 */

// Plugins
import { loadFonts } from "./webfontloader";
import vuetify from "./vuetify";
import pinia from "../store";
import router from "../router";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import IntroJs from 'intro.js'
import 'intro.js/introjs.css';

// Types
import type { App } from "vue";

export function registerPlugins(app: App) {
  loadFonts();
  app.use(IntroJs).use(vuetify).use(router).use(pinia).use(ElementPlus);
}

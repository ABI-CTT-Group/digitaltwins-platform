/**
 * plugins/index.ts
 *
 * Automatically included in `./src/main.ts`
 */

// Plugins
import { loadFonts } from "./webfontloader";
import vuetify from "./vuetify";
import { useTheme } from "vuetify";
import pinia from "../store";
import router from "../router";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import IntroJs from 'intro.js'
import 'intro.js/introjs.css';
import { defineStore, storeToRefs} from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import * as Vue from 'vue'

// Types
import type { App } from "vue";

export function registerPlugins(app: App) {
  loadFonts();
  pinia.use(piniaPluginPersistedstate);
  ;(window as any).Vue = Vue;
  ;(window as any).Vuetify = vuetify;
  ;(window as any).defineStore = defineStore;
  ;(window as any).storeToRefs = storeToRefs;
  ;(window as any).useTheme = useTheme;
  app.use(IntroJs).use(vuetify).use(router).use(pinia).use(ElementPlus);
}

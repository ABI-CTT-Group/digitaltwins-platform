/**
 * plugins/index.ts
 *
 * Automatically included in `./src/main.ts`
 */

// Plugins
import { loadFonts } from "./webfontloader";
import vuetify from "./vuetify";
import { useTheme, useDisplay } from "vuetify";
import pinia from "../store";
import router from "../router";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import IntroJs from 'intro.js'
import 'intro.js/introjs.css';
import { createPinia, defineStore, storeToRefs, getActivePinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import * as Vue from 'vue'
// Types
import type { App } from "vue";
import Toast, { createToastInterface, useToast, TYPE, POSITION } from 'vue-toastification';
import 'vue-toastification/dist/index.css';


export function registerPlugins(app: App) {
  loadFonts();
  pinia.use(piniaPluginPersistedstate);
  ; (window as any).Vue = Vue;
  ; (window as any).Pinia = { createPinia, defineStore, storeToRefs, getActivePinia };
  ; (window as any).Vuetify = Object.assign(vuetify, { useTheme, useDisplay });
  ; (window as any).VueToastification = { default: Toast, createToastInterface, useToast, TYPE, POSITION };
  app.use(IntroJs).use(vuetify).use(router).use(pinia).use(ElementPlus).use(Toast);
}

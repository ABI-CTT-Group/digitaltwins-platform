/**
 * main.ts
 *
 * Bootstraps Vuetify and other plugins then mounts the App`
 */

// Components
import App from "./App.vue";
import "@/styles/style.css";

// Composables
import { createApp } from "vue";

// Plugins
import { registerPlugins } from "@/plugins";
import { initKeycloak } from "@/plugins/keycloak";


const app = createApp(App);

// Initialize Keycloak and then register plugins and mount app
initKeycloak()
  .then(() => {
    registerPlugins(app);
    app.mount("#app");
  })
  .catch((error) => {
    console.error("Failed to initialize Keycloak:", error);
    // Still mount the app in case of keycloak init error
    registerPlugins(app);
    app.mount("#app");
  });




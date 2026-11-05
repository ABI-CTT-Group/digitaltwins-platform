/**
 * main.ts
 *
 * Bootstraps Vuetify and other plugins then mounts the App`
 */

// Components
import App from "./App.vue";
// Self-hosted fonts: airgapped installs can't reach Google Fonts.
import "@fontsource-variable/hanken-grotesk";
import "@fontsource-variable/fraunces";
import "@/styles/style.css";

// Composables
import { createApp } from "vue";

// Plugins
import { registerPlugins } from "@/bootstrap";
import { initKeycloak, setupIdleTimeout } from "@/bootstrap/keycloak";


const app = createApp(App);

// Initialize Keycloak and then register plugins and mount app
initKeycloak()
  .then(() => {
    // Setup idle timeout: logout after 30 minutes of inactivity
    setupIdleTimeout(30);
    
    registerPlugins(app);
    app.mount("#app");
  })
  .catch((error) => {
    console.error("Failed to initialize Keycloak:", error);
    // Still mount the app in case of keycloak init error
    registerPlugins(app);
    app.mount("#app");
  });




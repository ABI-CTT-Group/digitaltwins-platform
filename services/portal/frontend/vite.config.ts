// Plugins
import vue from "@vitejs/plugin-vue";
import vuetify, { transformAssetUrls } from "vite-plugin-vuetify";
import glslify from "rollup-plugin-glslify";
import { VitePWA } from "vite-plugin-pwa";

// Utilities
import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";

const filesNeedToExclude = ["src/ts"];

const filesPathToExclude = filesNeedToExclude.map((src) => {
  return fileURLToPath(new URL(src, import.meta.url));
});

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue({
      template: {
        transformAssetUrls,
        compilerOptions: {
          isCustomElement: (tag) => tag.startsWith("ion-"),
        },
      },
    }),
    // https://github.com/vuetifyjs/vuetify-loader/tree/next/packages/vite-plugin
    vuetify({
      autoImport: true,
      styles: {
        configFile: "src/styles/settings.scss",
      },
    }),
    glslify({
      // Default
      include: ["**/*.vs", "**/*.fs", "**/*.vert", "**/*.frag", "**/*.glsl"],
      // Undefined by default
      exclude: "node_modules/**",
      // Compress shader by default using logic from rollup-plugin-glsl
      compress: true,
    }),
    // PWA — keeps the DigitalTWINS Portal installable / full-screen
    // (standalone display) via the web app manifest below, but the service
    // worker does NO caching. It precaches nothing and serves every request
    // network-only, so a plain browser refresh after a redeploy always loads
    // the freshest code — no "empty cache and hard refresh" needed. The SW
    // exists only to satisfy the browser installability criteria.
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "auto",
      // Don't run the SW under `vite dev` — it would interfere with the
      // Keycloak redirect/iframe flow and hot reload.
      devOptions: { enabled: false },
      // No `includeAssets` — we don't want the SW precaching icons/fonts
      // either. The icons referenced by the manifest below live in public/
      // and are served over the network; they don't need to be cached.
      manifest: {
        id: "/",
        name: "DigitalTWINS Portal",
        short_name: "DigitalTWINS",
        description:
          "DigitalTWINS — clinical digital-twin platform: register, build and run medical imaging and measurement plugins.",
        lang: "en",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "any",
        theme_color: "#06121a",
        background_color: "#06101a",
        icons: [
          {
            src: "digitaltwins-icon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any",
          },
          { src: "pwa-192x192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "pwa-512x512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          {
            src: "pwa-maskable-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // Precache NOTHING — we never want the SW to serve a stale asset.
        globPatterns: [],
        // No SW-side SPA navigation fallback; nginx already does try_files,
        // and a fallback would risk serving a cached shell.
        navigateFallback: null,
        // Wipe any precache left behind by the previous caching service
        // worker so returning clients are cleaned up automatically.
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
        // Every request goes straight to the network and is never stored.
        // This keeps a fetch handler present (required for installability)
        // while guaranteeing zero caching.
        runtimeCaching: [
          {
            urlPattern: /.*/,
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
  define: {
    "process.env": {
      // BASE_URL: "/Tumour_Tracking_App/",
      BASE_URL: "/",
    },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
    extensions: [".js", ".json", ".jsx", ".mjs", ".ts", ".tsx", ".vue"],
  },
  // base: "/Tumour_Tracking_App/",
  base: "/",
  build: {
    outDir: "./build",
    rollupOptions: {
      external: [...filesPathToExclude]
    }
  },
  optimizeDeps: {
    exclude: [
      '@vuetify/loader-shared/runtime',
      'vuetify',
    ],
  },
  server: {
    host: "0.0.0.0",
    port: 80,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  preview: {
    port: 3000,
  },
});

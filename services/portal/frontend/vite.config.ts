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
    // PWA — installable DigitalTWINS Portal with an app-shell-only service
    // worker. The SW precaches ONLY the built static shell (JS/CSS/fonts/icons).
    // Everything dynamic in this portal — Keycloak auth, the streaming /api,
    // the runtime /plugin UMD bundles, the public /tools (MinIO) bucket and the
    // /minio-console — must never be served stale, so they are kept network-only
    // (not precached) and excluded from the SPA navigation fallback below.
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "auto",
      // Don't run the SW under `vite dev` — it would interfere with the
      // Keycloak redirect/iframe flow and hot reload.
      devOptions: { enabled: false },
      includeAssets: [
        "favicon.ico",
        "digitaltwins-mark.svg",
        "digitaltwins-icon.svg",
        "digitaltwins-maskable.svg",
        "apple-touch-icon.png",
        "pwa-192x192.png",
        "pwa-512x512.png",
        "pwa-maskable-512x512.png",
      ],
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
        // Precache the built app shell only (code + styles + fonts + icons).
        // Bundled raster content (the large hashed assets/*.png screenshots) is
        // deliberately excluded — those load over the network when online and
        // would bloat the SW install. The small PWA icon PNGs are precached via
        // `includeAssets` above instead.
        globPatterns: ["**/*.{js,css,html,woff,woff2,ttf,svg}"],
        // Keep heavy/static public assets out of the precache.
        globIgnores: ["**/*.pdf", "pdfjs/**", "eps/**", "plugins/**"],
        // The main bundle is ~2.2 MiB; raise the cap so the shell precaches.
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
        // SPA fallback for client-side routes, but NEVER hijack portal routes
        // that nginx proxies to the backend / MinIO, the Keycloak SSO iframe,
        // or any file request with an extension.
        navigateFallback: "index.html",
        navigateFallbackDenylist: [
          /^\/api(\/|$)/,
          /^\/plugin(\/|$)/,
          /^\/tools(\/|$)/,
          /^\/minio-console(\/|$)/,
          /^\/realms(\/|$)/,
          /silent-check-sso\.html$/,
          /\/[^/?]+\.[^/]+$/,
        ],
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
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

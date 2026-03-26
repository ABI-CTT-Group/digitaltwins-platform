// Plugins
import vue from "@vitejs/plugin-vue";
import vuetify, { transformAssetUrls } from "vite-plugin-vuetify";
import glslify from "rollup-plugin-glslify";

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
    port: 3000,
  },
  preview: {
    port: 3000,
  },
});

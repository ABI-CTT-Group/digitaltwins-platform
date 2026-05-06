"""
Unit tests for the per-expose store namespacing + externalize validation in
PluginBuilder._update_vite_config (Phase 2 of plugin state isolation work).

Run from `clinical-dashboard/backend/`:
    python -m unittest tests.test_vite_config_injection
"""
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Make `app.*` importable when running tests from the backend root.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Avoid creating plugin_registry.db in the source tree during import.
os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from app.builder.build_tool import PluginBuilder  # noqa: E402


CONFIG_EMPTY_PLUGINS = """\
import { defineConfig } from 'vite'
export default defineConfig({
  plugins: [],
  build: {
    lib: { entry: './src/index.ts', name: 'X', formats: ['umd'], fileName: (format) => `my-app.${format}.js` },
    rollupOptions: {
      external: ['vue', 'pinia', 'vuetify', 'vue-toastification'],
      output: { globals: { vue: 'Vue', pinia: 'Pinia', vuetify: 'Vuetify', 'vue-toastification': 'VueToastification' } },
    },
  },
})
"""

CONFIG_VUE_ONLY = """\
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  build: {
    lib: { entry: './src/index.ts', name: 'X', formats: ['umd'], fileName: (format) => `my-app.${format}.js` },
    rollupOptions: {
      external: ['vue', 'pinia', 'vuetify', 'vue-toastification'],
      output: { globals: { vue: 'Vue', pinia: 'Pinia', vuetify: 'Vuetify', 'vue-toastification': 'VueToastification' } },
    },
  },
})
"""

CONFIG_VUE_PLUS_OTHERS = """\
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
  ],
  build: {
    lib: { entry: './src/index.ts', name: 'X', formats: ['umd'], fileName: (format) => `my-app.${format}.js` },
    rollupOptions: {
      external: ['vue', 'pinia', 'vuetify', 'vue-toastification'],
      output: { globals: { vue: 'Vue', pinia: 'Pinia', vuetify: 'Vuetify', 'vue-toastification': 'VueToastification' } },
    },
  },
})
"""

CONFIG_NO_PLUGINS_ARRAY = """\
import { defineConfig } from 'vite'
export default defineConfig({
  build: {
    lib: { entry: './src/index.ts', name: 'X', formats: ['umd'], fileName: (format) => `my-app.${format}.js` },
    rollupOptions: {
      external: ['vue', 'pinia', 'vuetify', 'vue-toastification'],
    },
  },
})
"""

CONFIG_NO_EXTERNAL = """\
import { defineConfig } from 'vite'
export default defineConfig({
  plugins: [],
  build: {
    lib: { entry: './src/index.ts', name: 'X', formats: ['umd'], fileName: (format) => `my-app.${format}.js` },
  },
})
"""

CONFIG_PARTIAL_EXTERNAL = """\
import { defineConfig } from 'vite'
export default defineConfig({
  plugins: [],
  build: {
    lib: { entry: './src/index.ts', name: 'X', formats: ['umd'], fileName: (format) => `my-app.${format}.js` },
    rollupOptions: { external: ['vue', 'pinia'] },
  },
})
"""

CONFIG_CONDITIONAL_EXTERNAL = """\
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
const filesPathToExclude = []
export default defineConfig(({ command }) => {
  const isPluginBuild = process.env.BUILD_AS_PLUGIN === 'true'
  return {
    plugins: [vue()],
    build: isPluginBuild
      ? {
          lib: { entry: './src/index.ts', name: 'X', formats: ['umd'], fileName: (format) => `my-app.${format}.js` },
          rollupOptions: {
            external: ['vue', 'vuetify', 'pinia', 'vue-toastification'],
            output: { globals: { vue: 'Vue', vuetify: 'Vuetify', pinia: 'Pinia', 'vue-toastification': 'VueToastification' } },
          },
        }
      : { rollupOptions: { external: [...filesPathToExclude] } },
  }
})
"""


class StoreNamespaceSnippetTests(unittest.TestCase):
    def test_snippet_embeds_expose_prefix(self):
        snippet = PluginBuilder._build_store_namespace_plugin_snippet("annotator-a")
        self.assertIn("'annotator-a__'", snippet)
        self.assertIn("portal-plugin-store-namespace", snippet)
        self.assertIn("enforce: 'pre'", snippet)

    def test_snippet_strips_unsafe_chars_from_expose(self):
        snippet = PluginBuilder._build_store_namespace_plugin_snippet("evil';name//")
        self.assertNotIn("evil';name", snippet)
        self.assertIn("'evilname__'", snippet)


class InjectStoreNamespacePluginTests(unittest.TestCase):
    def _write_config(self, content: str) -> Path:
        td = Path(self.tmpdir.name)
        cfg = td / "vite.config.ts"
        cfg.write_text(content, encoding="utf-8")
        return cfg

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_inject_into_empty_plugins_array(self):
        cfg = self._write_config(CONFIG_EMPTY_PLUGINS)
        ok = PluginBuilder._inject_store_namespace_plugin(cfg, "expose-a")
        self.assertTrue(ok)
        out = cfg.read_text(encoding="utf-8")
        self.assertIn("portal-plugin-store-namespace", out)
        self.assertIn("'expose-a__'", out)

    def test_inject_into_vue_only(self):
        cfg = self._write_config(CONFIG_VUE_ONLY)
        ok = PluginBuilder._inject_store_namespace_plugin(cfg, "expose-b")
        self.assertTrue(ok)
        out = cfg.read_text(encoding="utf-8")
        # Plugin should appear before the vue() call.
        ns_idx = out.index("portal-plugin-store-namespace")
        vue_idx = out.index("vue()")
        self.assertLess(ns_idx, vue_idx, "namespace plugin must precede vue() in plugins array")

    def test_inject_into_vue_plus_others(self):
        cfg = self._write_config(CONFIG_VUE_PLUS_OTHERS)
        ok = PluginBuilder._inject_store_namespace_plugin(cfg, "expose-c")
        self.assertTrue(ok)
        out = cfg.read_text(encoding="utf-8")
        self.assertEqual(out.count("portal-plugin-store-namespace"), 1)
        self.assertIn("vue()", out)
        self.assertIn("vueJsx()", out)

    def test_idempotent_does_not_double_inject(self):
        cfg = self._write_config(CONFIG_VUE_PLUS_OTHERS)
        self.assertTrue(PluginBuilder._inject_store_namespace_plugin(cfg, "expose-d"))
        self.assertTrue(PluginBuilder._inject_store_namespace_plugin(cfg, "expose-d"))
        out = cfg.read_text(encoding="utf-8")
        self.assertEqual(out.count("portal-plugin-store-namespace"), 1)

    def test_returns_false_when_no_plugins_array(self):
        cfg = self._write_config(CONFIG_NO_PLUGINS_ARRAY)
        ok = PluginBuilder._inject_store_namespace_plugin(cfg, "expose-e")
        self.assertFalse(ok)
        # Original content untouched.
        self.assertNotIn("portal-plugin-store-namespace", cfg.read_text(encoding="utf-8"))


class ValidateExternalizeTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def _write(self, content: str) -> Path:
        cfg = Path(self.tmpdir.name) / "vite.config.ts"
        cfg.write_text(content, encoding="utf-8")
        return cfg

    def test_passes_with_all_required_deps(self):
        # Should not raise.
        PluginBuilder._validate_externalize(self._write(CONFIG_VUE_PLUS_OTHERS))

    def test_passes_with_conditional_external(self):
        # Even when external is inside a conditional branch, validation pools
        # all `external: [...]` blocks and finds the required deps.
        PluginBuilder._validate_externalize(self._write(CONFIG_CONDITIONAL_EXTERNAL))

    def test_raises_when_external_block_absent(self):
        with self.assertRaises(RuntimeError) as ctx:
            PluginBuilder._validate_externalize(self._write(CONFIG_NO_EXTERNAL))
        self.assertIn("no `external", str(ctx.exception))

    def test_raises_when_required_dep_missing(self):
        with self.assertRaises(RuntimeError) as ctx:
            PluginBuilder._validate_externalize(self._write(CONFIG_PARTIAL_EXTERNAL))
        msg = str(ctx.exception)
        self.assertIn("vuetify", msg)
        self.assertIn("vue-toastification", msg)


class UpdateViteConfigEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_full_pipeline_on_realistic_config(self):
        project_dir = Path(self.tmpdir.name)
        cfg = project_dir / "vite.config.ts"
        cfg.write_text(textwrap.dedent("""\
            import { defineConfig } from 'vite'
            import vue from '@vitejs/plugin-vue'
            export default defineConfig({
              plugins: [vue()],
              build: {
                lib: { entry: './src/index.ts', name: 'OldName', formats: ['es'], fileName: (format) => `old-name.${format}.js` },
                rollupOptions: {
                  external: ['vue', 'pinia', 'vuetify', 'vue-toastification'],
                },
              },
            })
        """), encoding="utf-8")

        builder = PluginBuilder(dataset_dir=str(project_dir / "datasets"))
        builder._update_vite_config(project_dir, "annotator-x")

        out = cfg.read_text(encoding="utf-8")
        # _replace_vite_build_config rewrote name/formats/fileName.
        self.assertIn("'annotator-x'", out)
        self.assertIn("formats: ['umd']", out)
        self.assertIn("`my-app.${format}.js`", out)
        # _inject_store_namespace_plugin added the namespacing plugin.
        self.assertIn("portal-plugin-store-namespace", out)
        self.assertIn("'annotator-x__'", out)

    def test_full_pipeline_fails_when_externalize_missing(self):
        project_dir = Path(self.tmpdir.name)
        cfg = project_dir / "vite.config.ts"
        cfg.write_text(CONFIG_PARTIAL_EXTERNAL, encoding="utf-8")
        builder = PluginBuilder(dataset_dir=str(project_dir / "datasets"))
        with self.assertRaises(RuntimeError):
            builder._update_vite_config(project_dir, "annotator-y")


if __name__ == "__main__":
    unittest.main()

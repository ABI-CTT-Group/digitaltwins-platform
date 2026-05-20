<template>
  <div ref="container" />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { createApp, type App } from 'vue'
import { createPinia } from 'pinia'
import vuetify from '@/bootstrap/vuetify'
// @ts-ignore - vue-toastification is installed but missing type declarations
import Toast, { useToast } from 'vue-toastification'
import ElementPlus from 'element-plus'

const props = defineProps<{
  src: string
  expose: string
}>()

const container = ref<HTMLElement | null>(null)
let pluginApp: App | null = null
let scriptEl: HTMLScriptElement | null = null

// Per-mount Pinia: every entry creates a fresh instance so plugin state is
// reset on exit and never leaks across plugins. Vuetify / Toast / ElementPlus
// are intentionally shared with portal — they are stateless / singleton UI
// containers, isolating them would split the toast queue and theme.
// Portal does not currently `provide()` anything to plugins (verified in plan
// 01 phase 0); if that changes, forward keys with `pluginApp.provide(...)`
// before mount.

onMounted(async () => {
  scriptEl = await loadScript(props.src)
  const Root = (window as any)[props.expose]
  if (!Root) {
    throw new Error(`Plugin expose '${props.expose}' not found on window`)
  }
  pluginApp = createApp(Root)
  pluginApp.use(createPinia())
  pluginApp.use(vuetify)
  pluginApp.use(Toast)
  pluginApp.use(ElementPlus)
  pluginApp.mount(container.value!)
})

onBeforeUnmount(() => {
  try {
    pluginApp?.unmount()
  } catch (e) {
    console.warn('plugin unmount failed', e)
  }
  pluginApp = null
  scriptEl?.remove()
  scriptEl = null
  delete (window as any)[props.expose]
  try {
    useToast().clear()
  } catch {
    // toast not initialised on this page; safe to ignore
  }
})

function loadScript(src: string) {
  return new Promise<HTMLScriptElement>((resolve, reject) => {
    const s = document.createElement('script')
    s.src = src
    s.onload = () => resolve(s)
    s.onerror = reject
    document.head.appendChild(s)
  })
}
</script>

<style scoped></style>

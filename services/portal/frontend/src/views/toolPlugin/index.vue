<template>
    <v-container class="d-flex w-100 h-100">
        <v-card class="ma-auto" max-width="500">
            <v-toolbar color="pink">
                <v-btn icon="mdi-menu"></v-btn>

                <v-toolbar-title>Plugins</v-toolbar-title>

                <v-btn icon="mdi-magnify"></v-btn>

                <v-btn icon="mdi-checkbox-marked-circle"></v-btn>
            </v-toolbar>

            <v-list v-model:selected="selected" select-strategy="leaf">
            <v-list-item
                v-for="item, i in items"
                :key="i"
                :value="i"
                active-class="text-pink"
                class="py-3"
                @click="()=>handleItemClick(item)"
            >
                <v-list-item-title>{{ item.name }}</v-list-item-title>

                <v-list-item-subtitle class="text-high-emphasis">{{ item.description }}</v-list-item-subtitle>

                <template v-slot:append="{ isSelected }">
                <v-list-item-action class="flex-column align-end">
                    <small class="mb-4 text-high-emphasis opacity-60">explore</small>

                    <v-spacer></v-spacer>

                    <v-icon v-if="isSelected" color="yellow-darken-3">mdi-star</v-icon>

                    <v-icon v-else class="opacity-30">mdi-star-outline</v-icon>
                </v-list-item-action>
                </template>
            </v-list-item>
            </v-list>
        </v-card>
    </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, shallowRef } from 'vue'
import { useRemoteAppStore } from '@/store/remoteStore'
import { useRouter } from 'vue-router'
import { useToolMetadata } from '@/plugins/plugin_api'

const router = useRouter()

type Item = {
    name: string;
    path: string;
    expose: string;
    description: string;
}

const items = ref<Item[]>([])
const selected = shallowRef([0])
const remoteAppStore = useRemoteAppStore()


onMounted(async () => {
  try {
    const data = await useToolMetadata()
    if (Array.isArray(data.components)) {
      items.value = data.components
    } else {
      console.warn('metadata components is not an array')
    }
  } catch (err) {
    console.error('Error loading tool metadata:', err)
  }
})

const handleItemClick = (item: Item) => {
  remoteAppStore.setRemoteApp(item)
  router.push({
    name: 'ToolPluginView'
  })
}
</script>

<style scoped>
.file-list-container {
  max-width: 600px;
  margin: 40px auto;
  padding: 24px;
  background: #f9f9fb;
  border-radius: 12px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
  font-family: 'Segoe UI', sans-serif;
}

.file-list-container h2 {
  font-size: 1.6rem;
  margin-bottom: 20px;
  color: #333;
  text-align: center;
}

.file-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.file-item {
  margin-bottom: 12px;
  padding: 12px 16px;
  background: white;
  border-radius: 8px;
  transition: transform 0.2s, box-shadow 0.2s;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
}

.file-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.file-link {
  text-decoration: none;
  color: #007acc;
  font-weight: 500;
  word-break: break-all;
}

.file-link:hover {
  text-decoration: underline;
}
</style>

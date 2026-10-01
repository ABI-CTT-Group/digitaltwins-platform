<template>
  <v-dialog v-model="open" max-width="560" :persistent="!!deleting" transition="dialog-bottom-transition">
    <v-card rounded="lg" flat class="overflow-hidden">
      <v-card-title class="d-flex align-center px-6 pt-6 pb-4 text-h5">
        <v-icon color="#ff6b6b" class="mr-3" size="32">mdi-trash-can-outline</v-icon>
        Delete {{ kind }} from the platform
      </v-card-title>

      <v-card-text class="px-6 pb-4 text-body-2">
        <p class="mb-4">
          <strong>{{ item?.name }}</strong> is removed from the platform: its dataset, SEEK entry and FHIR resources.
          This cannot be undone.
        </p>

        <template v-if="kind === 'workflow'">
          <v-progress-linear v-if="loadingTools" indeterminate :color="accent" class="mb-4" />
          <template v-else-if="tools.length">
            <p class="mb-2">It runs {{ tools.length }} tool dataset{{ tools.length === 1 ? '' : 's' }}:</p>
            <ul class="mb-4 ms-6">
              <li v-for="t in tools" :key="t.datasetUuid">
                {{ t.datasetName || t.datasetUuid }}
                <span v-if="t.stepIds?.length" class="text-medium-emphasis">(step {{ t.stepIds.join(', ') }})</span>
              </li>
            </ul>
            <p class="mb-2">Delete them as well, or keep them as standalone tools?</p>
          </template>
        </template>

        <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-2 text-body-2">
          {{ error }}
        </v-alert>
      </v-card-text>

      <v-divider :thickness="2" />
      <v-card-actions class="px-6 py-4 justify-center flex-wrap">
        <v-btn data-testid="cancel" variant="text" color="#9fb4bf" class="text-none mx-2" rounded="lg"
               text="Cancel" :disabled="!!deleting" @click="open = false" />
        <template v-if="kind === 'workflow'">
          <v-btn data-testid="delete-workflow-only" variant="tonal" :color="tools.length ? accent : '#ff6b6b'"
                 class="text-none mx-2" rounded="lg" :loading="deleting === 'workflow'"
                 :disabled="loadingTools || !!deleting"
                 :text="tools.length ? 'Delete workflow only' : 'Delete workflow'" @click="remove(false)" />
          <v-btn v-if="tools.length" data-testid="delete-with-tools" variant="tonal" color="#ff6b6b"
                 class="text-none mx-2" rounded="lg" :loading="deleting === 'all'" :disabled="!!deleting"
                 :text="`Delete workflow and its ${tools.length} tool${tools.length === 1 ? '' : 's'}`"
                 @click="remove(true)" />
        </template>
        <v-btn v-else data-testid="delete-tool" variant="tonal" color="#ff6b6b" class="text-none mx-2"
               rounded="lg" :loading="!!deleting" :disabled="!!deleting" text="Delete tool" @click="remove()" />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PlatformLink } from '@/models/types'
import { datasetInUse, deletePlatformDataset, useWorkflowTools } from '@/bootstrap/platform_api'

// Confirms deleting a dataset uploaded to the platform directly. For a workflow it
// lists the tool datasets its steps run and asks whether they go too.
const open = defineModel<boolean>({ default: false })
const props = defineProps<{ kind: 'workflow' | 'tool'; item: { uuid: string; name: string } | null }>()
const emit = defineEmits<{ deleted: [uuid: string] }>()

const accent = computed(() => (props.kind === 'workflow' ? '#7fb2f0' : '#5fd6e8'))
const tools = ref<PlatformLink[]>([])
const loadingTools = ref(false)
const deleting = ref<false | 'workflow' | 'all'>(false)
const error = ref('')

const errorText = (err: any): string => {
  const inUse = datasetInUse(err)
  if (inUse?.workflows.length) {
    return `Used by workflow(s): ${inUse.workflows.map((w) => w.datasetName || w.datasetUuid).join(', ')}. Delete the workflow first.`
  }
  if (inUse) return inUse.message
  const detail = err?.response?.data?.detail
  return typeof detail === 'string' ? detail : err?.message || 'Delete failed.'
}

watch(
  () => [open.value, props.item?.uuid] as const,
  async ([isOpen, uuid]) => {
    if (!isOpen || !uuid) return
    tools.value = []
    error.value = ''
    deleting.value = false
    if (props.kind !== 'workflow') return
    loadingTools.value = true
    try {
      tools.value = await useWorkflowTools(uuid)
    } catch (err) {
      error.value = errorText(err)
    } finally {
      loadingTools.value = false
    }
  },
  { immediate: true },
)

const remove = async (deleteTools?: boolean) => {
  if (!props.item) return
  deleting.value = deleteTools ? 'all' : 'workflow'
  error.value = ''
  try {
    await deletePlatformDataset(props.item.uuid, deleteTools)
    emit('deleted', props.item.uuid)
    open.value = false
  } catch (err) {
    error.value = errorText(err)
  } finally {
    deleting.value = false
  }
}
</script>

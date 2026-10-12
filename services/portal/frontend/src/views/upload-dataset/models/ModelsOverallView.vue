<template>
  <RegistryView
    ref="registryRef"
    register-label="Register a new model"
    search-label="Search models"
    accent="#b08fe8"
    :fetch-list="useModels"
    :is-pending="hasPendingItem"
    @register="emit('register')"
  >
    <template #default="{ items }">
      <ModelCard
        v-for="m in items"
        :key="m.id"
        :model="m"
        @resume-upload="(id: string) => emit('resume', id)"
        @cancel-upload="handleCancelUpload"
        @approve="openApproval"
        @edit="(model: MeasurementResponse) => emit('edit', model)"
        @retry-fhir="handleRetryFhir"
        @delete="openDelete"
      />
    </template>
  </RegistryView>

  <v-dialog v-model="approvalOpen" max-width="560" :persistent="approving">
    <v-card flat class="pa-2">
      <v-card-title class="dialog-title">Approve & register?</v-card-title>
      <v-card-text>
        <strong>"{{ approvalModel?.name }}"</strong> is stored in MinIO and the platform database
        <span v-if="approvalModel?.hasAnnotation">and published to FHIR as a Device</span>.
        Assays and inference workflows can then use it by its dataset UUID.
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" color="#9fb4bf" class="text-none" :disabled="approving" @click="approvalOpen = false">Cancel</v-btn>
        <v-btn
          data-testid="approve"
          color="#b08fe8"
          variant="tonal"
          class="text-none"
          prepend-icon="mdi-cloud-upload"
          :loading="approving"
          @click="handleApprove"
        >
          Approve & register
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <DeletePlatformDatasetDialog v-model="deleteOpen" kind="model" :item="deleteItem" @deleted="handleDeleted" />
</template>

<script setup lang="ts">
// @ts-ignore - vue-toastification ships without type declarations
import { useToast } from 'vue-toastification';
import { ref } from 'vue';
import RegistryView from '../components/RegistryView.vue';
import DeletePlatformDatasetDialog from '../components/DeletePlatformDatasetDialog.vue';
import ModelCard from './components/ModelCard.vue';
import { useModels } from '@/bootstrap/model_api';
import { useMeasurementRetryFhir, useMeasurementSubmit, useUploadCancel } from '@/bootstrap/measurement_api';
import type { MeasurementResponse } from '@/models/types';

const toast = useToast();
const emit = defineEmits<{
  (e: 'register'): void;
  (e: 'resume', id: string): void;
  (e: 'edit', m: MeasurementResponse): void;
}>();

const registryRef = ref<{ handleRefresh: () => Promise<void> }>();
const refresh = () => registryRef.value?.handleRefresh();

// Keep polling while an upload, approval or FHIR push is in flight.
const hasPendingItem = (items: MeasurementResponse[]) =>
  items.some((m) => m.status === 'uploading' || m.status === 'pending_upload');

const detail = (e: any) => e?.response?.data?.detail || e?.message || 'unknown error';

const handleCancelUpload = async (id: string) => {
  try {
    await useUploadCancel(id);
    toast.success('Upload cancelled.');
  } catch (e) {
    toast.error(`Cancel failed: ${detail(e)}`);
  } finally {
    await refresh();
  }
};

const handleRetryFhir = async (id: string) => {
  try {
    await useMeasurementRetryFhir(id);
    toast.success('Publishing the model to FHIR.');
  } catch (e) {
    toast.error(`Retry FHIR failed: ${detail(e)}`);
  } finally {
    await refresh();
  }
};

const approvalOpen = ref(false);
const approvalModel = ref<MeasurementResponse | null>(null);
const approving = ref(false);
const openApproval = (m: MeasurementResponse) => {
  approvalModel.value = m;
  approvalOpen.value = true;
};
const handleApprove = async () => {
  if (!approvalModel.value) return;
  approving.value = true;
  try {
    await useMeasurementSubmit(approvalModel.value.id);
    toast.success('Registering the model.');
    approvalOpen.value = false;
  } catch (e) {
    toast.error(`Approval failed: ${detail(e)}`);
  } finally {
    approving.value = false;
    await refresh();
  }
};

const deleteOpen = ref(false);
const deleteItem = ref<{ uuid: string; name: string } | null>(null);
const openDelete = (m: MeasurementResponse) => {
  deleteItem.value = { uuid: m.uuid!, name: m.name };
  deleteOpen.value = true;
};
const handleDeleted = async () => {
  toast.success('Model deleted.');
  await refresh();
};
</script>

<style scoped>
.dialog-title {
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
}
</style>

<template>
  <RegistryView
    ref="registryRef"
    register-label="Register a model"
    search-label="Search models"
    accent="var(--accent-models)"
    :fetch-list="useModels"
    :is-pending="hasPendingItem"
    :filter-fn="hub.filterFn.value"
    :sort-fn="hub.sortFn"
    @refresh="hub.onRefresh"
    @register="router.push({ name: 'RegisterModel' })"
  >
    <template #filters>
      <HubFilterChips v-model="hub.filter.value" :counts="hub.counts.value" />
    </template>

    <template #default="{ items }">
      <ModelCard
        v-for="m in items"
        :key="m.id"
        :model="m"
        @resume-upload="(id: string) => router.push(registerRoute('models', id, 'upload'))"
        @cancel-upload="confirmCancelUpload"
        @approve="openApproval"
        @edit="(model: MeasurementResponse) => router.push(registerRoute('models', model.id, 'annotation'))"
        @retry-fhir="handleRetryFhir"
        @delete="openDelete"
      />
    </template>

    <template #empty>
      <p class="hub-empty">No models yet. Register a trained model so assays and inference workflows can use it.</p>
    </template>
  </RegistryView>

  <ConfirmDialog v-if="confirm.request.value" v-model="confirm.open.value" v-bind="confirm.request.value" />

  <ApproveDialog v-model="approvalOpen" category="models" :item="approvalModel" @finished="refresh" />

  <DeletePlatformDatasetDialog v-model="deleteOpen" kind="model" :item="deleteItem" @deleted="handleDeleted" />
</template>

<script setup lang="ts">
// @ts-ignore - vue-toastification ships without type declarations
import { useToast } from 'vue-toastification';
import { ref } from 'vue';
import RegistryView from '../components/RegistryView.vue';
import DeletePlatformDatasetDialog from '../components/DeletePlatformDatasetDialog.vue';
import ApproveDialog from '../components/ApproveDialog.vue';
import ConfirmDialog from '../components/ConfirmDialog.vue';
import HubFilterChips from '../components/HubFilterChips.vue';
import { useConfirm } from '../components/useConfirm';
import { datasetStatus } from '../components/cardStatus';
import { useHubFilter } from '../components/hubFilter';
import { registerRoute } from '../components/registrationSteps';
import { describeApiError } from '../components/apiError';
import { useRouter } from 'vue-router';
import ModelCard from './components/ModelCard.vue';
import { useModels } from '@/bootstrap/model_api';
import { useMeasurementRetryFhir, useUploadCancel } from '@/bootstrap/measurement_api';
import type { MeasurementResponse } from '@/models/types';

const toast = useToast();
const router = useRouter();

const registryRef = ref<{ handleRefresh: () => Promise<void> }>();
const refresh = () => registryRef.value?.handleRefresh();

// Keep polling while an upload, approval or FHIR push is in flight.
const hasPendingItem = (items: MeasurementResponse[]) =>
  items.some((m) => m.status === 'uploading' || m.status === 'pending_upload');

// All · Needs you · In progress · In the platform, from each card's status line; what needs you first.
const hub = useHubFilter((m: MeasurementResponse) => datasetStatus(m));

const confirm = useConfirm();
const confirmCancelUpload = (m: MeasurementResponse) => confirm.ask({
  title: `Cancel the upload of ${m.name}?`,
  text: 'The parts uploaded so far are discarded. To register this model later, upload it again.',
  confirmLabel: 'Cancel upload',
  dismissLabel: 'Keep it',
  action: async () => {
    await useUploadCancel(m.id);
    toast.success('Upload cancelled.');
    await refresh();
  },
});

const handleRetryFhir = async (id: string) => {
  try {
    await useMeasurementRetryFhir(id);
    toast.success('Publishing the model to FHIR.');
  } catch (e) {
    toast.error(describeApiError(e, 'Retry FHIR'));
  } finally {
    await refresh();
  }
};

const approvalOpen = ref(false);
const approvalModel = ref<MeasurementResponse | null>(null);
const openApproval = (m: MeasurementResponse) => {
  approvalModel.value = m;
  approvalOpen.value = true;
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

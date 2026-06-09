<template>
  <RegistryView
    ref="registryRef"
    register-label="Register a new measurement dataset"
    search-label="Search measurements"
    accent="#62d3b0"
    :fetch-list="useMeasurement"
    :is-pending="hasPendingItem"
    @register="handleRegister"
  >
    <template #default="{ items }">
      <MeasurementCard
        v-for="m in items"
        :key="m.id"
        :measurement="m"
        @delete="handleDelete"
        @cancel-upload="handleCancelUpload"
        @resume-upload="handleResumeUpload"
        @retry-fhir="handleRetryFhir"
        @approve="handleApprove"
        @edit="handleEdit"
        @preview="handlePreview"
        @export="handleExport"
      />
    </template>
  </RegistryView>

  <ApprovalDialog
    v-model="approvalOpen"
    :measurement="approvalMeasurement"
    @finished="handleApprovalFinished"
  />
</template>

<script setup lang="ts">
// @ts-ignore - vue-toastification ships without type declarations
import { useToast } from 'vue-toastification';
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import RegistryView from '../components/RegistryView.vue';
import MeasurementCard from './components/MeasurementCard.vue';
import ApprovalDialog from './components/ApprovalDialog.vue';
import {
  useMeasurement,
  useDeleteMeasurement,
  useMeasurementRetryFhir,
  useMeasurementFhirPreview,
  useUploadCancel,
} from '@/bootstrap/measurement_api';
import type { MeasurementResponse } from '@/models/types';

const toast = useToast();
const router = useRouter();
const emit = defineEmits<{
  (e: 'register'): void;
  (e: 'resume', id: string): void;
  (e: 'edit', m: MeasurementResponse): void;
}>();

const registryRef = ref<{ handleRefresh: () => Promise<void> }>();

const approvalOpen = ref(false);
const approvalMeasurement = ref<MeasurementResponse | null>(null);

const handleRegister = () => emit('register');

// Auto-polling kicks in while ANY measurement is still in-flight. We pick a
// generous predicate (pending + uploading) so a row that's just been created
// but not yet submitted still triggers polling — same posture workflow uses.
const hasPendingItem = (items: MeasurementResponse[]) =>
  items.some(
    (m) => m.status === 'uploading' || m.status === 'pending' || m.status === 'pending_upload',
  );

const handleDelete = async (id: string) => {
  try {
    await useDeleteMeasurement(id);
    toast.success('Measurement deleted.');
  } catch (e) {
    console.error('Delete measurement failed:', e);
    toast.error('Failed to delete measurement.');
  } finally {
    await registryRef.value?.handleRefresh();
  }
};

// Resume = open the form bound to this specific unfinished upload (resume mode):
// name locked, no uniqueness check, dropped folder validated against the
// server's authoritative manifest. See InformationStep.
const handleResumeUpload = (id: string) => emit('resume', id);

// pending_upload rows are aborted through /upload/cancel (drops tmp parts + row),
// not the generic delete which assumes a fully-staged dataset.
const handleCancelUpload = async (id: string) => {
  try {
    await useUploadCancel(id);
    toast.success('Upload cancelled.');
  } catch (e) {
    console.error('Cancel upload failed:', e);
    toast.error('Failed to cancel upload.');
  } finally {
    await registryRef.value?.handleRefresh();
  }
};

const handleRetryFhir = async (id: string) => {
  try {
    await useMeasurementRetryFhir(id);
    toast.success('FHIR registration completed.');
  } catch (e: any) {
    console.error('Retry FHIR failed:', e);
    const detail = e?.response?.data?.detail || e?.message || 'Retry failed';
    toast.error(`Retry FHIR failed: ${detail}`);
  } finally {
    await registryRef.value?.handleRefresh();
  }
};

const handleApprove = (m: MeasurementResponse) => {
  approvalMeasurement.value = m;
  approvalOpen.value = true;
};

const handleApprovalFinished = async () => {
  await registryRef.value?.handleRefresh();
};

const handleEdit = (m: MeasurementResponse) => {
  // Re-enter the annotation form for this draft — index.vue owns the
  // list/form toggle, so bubble it up.
  emit('edit', m);
};

const handlePreview = (m: MeasurementResponse) => {
  router.push({ name: 'MeasurementFhirPreview', params: { id: m.id } });
};

const handleExport = async (m: MeasurementResponse) => {
  try {
    const fhir = await useMeasurementFhirPreview(m.id);
    const blob = new Blob([JSON.stringify(fhir, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${m.name || 'measurement'}-fhir.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e: any) {
    console.error('Export annotation failed:', e);
    const detail = e?.response?.data?.detail || e?.message || 'Export failed';
    toast.error(`Export failed: ${detail}`);
  }
};
</script>

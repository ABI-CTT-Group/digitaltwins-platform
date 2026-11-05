<template>
  <RegistryView
    ref="registryRef"
    register-label="Register a measurement dataset"
    search-label="Search measurements"
    accent="var(--accent-measurements)"
    :fetch-list="useMeasurement"
    :is-pending="hasPendingItem"
    :filter-fn="registrationFilterFn"
    @register="handleRegister"
  >
    <template #filters>
      <v-select
        v-model="registrationFilter"
        :items="registrationFilterOptions"
        item-title="title"
        item-value="value"
        label="Registration status"
        variant="outlined"
        base-color="#5f7884"
        color="#62d3b0"
        density="compact"
        hide-details
        style="width: 220px;"
      />
    </template>

    <template #default="{ items }">
      <MeasurementCard
        v-for="m in items"
        :key="m.id"
        :measurement="m"
        @delete="confirmDelete"
        @cancel-upload="confirmCancelUpload"
        @resume-upload="handleResumeUpload"
        @retry-fhir="handleRetryFhir"
        @approve="handleApprove"
        @edit="handleEdit"
        @preview="handlePreview"
        @export="handleExport"
      />
    </template>

    <template #empty>
      <p class="hub-empty">No measurement datasets yet. Register an SDS dataset so assays can use it as an input.</p>
    </template>
  </RegistryView>

  <ConfirmDialog v-if="confirm.request.value" v-model="confirm.open.value" v-bind="confirm.request.value" />

  <ApprovalDialog
    v-model="approvalOpen"
    :measurement="approvalMeasurement"
    @finished="handleApprovalFinished"
  />
</template>

<script setup lang="ts">
// @ts-ignore - vue-toastification ships without type declarations
import { useToast } from 'vue-toastification';
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import RegistryView from '../components/RegistryView.vue';
import MeasurementCard from './components/MeasurementCard.vue';
import ApprovalDialog from './components/ApprovalDialog.vue';
import ConfirmDialog from '../components/ConfirmDialog.vue';
import { useConfirm } from '../components/useConfirm';
import { clearExportFields } from './components/clearExportFields';
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

// "In platform" = a committed platform dataset (it has a uuid), whatever its FHIR
// state; uploads not committed yet are still drafts. MeasurementCard tags the same.
const isMeasurementInPlatform = (m: MeasurementResponse) => !!m.uuid;

const registrationFilterOptions = [
  { title: 'All', value: 'all' },
  { title: 'In platform', value: 'in-platform' },
  { title: 'Not in platform', value: 'not-in-platform' },
];
const registrationFilter = ref<'all' | 'in-platform' | 'not-in-platform'>('all');
const registrationFilterFn = computed(() => {
  if (registrationFilter.value === 'all') return undefined;
  const wantInPlatform = registrationFilter.value === 'in-platform';
  return (m: MeasurementResponse) => isMeasurementInPlatform(m) === wantInPlatform;
});

const confirm = useConfirm();
const confirmDelete = (m: MeasurementResponse) => confirm.ask({
  title: `Delete ${m.name}?`,
  text: isMeasurementInPlatform(m)
    ? 'The dataset is removed from the platform, with its FHIR resources. This can\'t be undone.'
    : 'The uploaded files and the FHIR annotation draft are discarded. This can\'t be undone.',
  confirmLabel: 'Delete dataset',
  action: async () => {
    await useDeleteMeasurement(m.id);
    toast.success('Measurement dataset deleted.');
    await registryRef.value?.handleRefresh();
  },
});

// Resume = open the form bound to this specific unfinished upload (resume mode):
// name locked, no uniqueness check, dropped folder validated against the
// server's authoritative manifest. See InformationStep.
const handleResumeUpload = (id: string) => emit('resume', id);

// pending_upload rows are aborted through /upload/cancel (drops tmp parts + row),
// not the generic delete which assumes a fully-staged dataset.
const confirmCancelUpload = (m: MeasurementResponse) => confirm.ask({
  title: `Cancel the upload of ${m.name}?`,
  text: 'The parts uploaded so far are discarded. To register this dataset later, upload it again.',
  confirmLabel: 'Cancel upload',
  dismissLabel: 'Keep it',
  action: async () => {
    await useUploadCancel(m.id);
    toast.success('Upload cancelled.');
    await registryRef.value?.handleRefresh();
  },
});

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
    // Strip server-assigned identifiers/URLs from the exported document:
    // all uuid + endpointUrl, and url inside attachments.
    const exported = clearExportFields(fhir);
    const blob = new Blob([JSON.stringify(exported, null, 2)], { type: 'application/json' });
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

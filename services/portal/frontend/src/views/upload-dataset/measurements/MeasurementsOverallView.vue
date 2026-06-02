<template>
  <RegistryView
    ref="registryRef"
    register-label="Register a new measurement dataset"
    search-label="Search measurements"
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
        @retry-fhir="handleRetryFhir"
      />
    </template>
  </RegistryView>
</template>

<script setup lang="ts">
// @ts-ignore - vue-toastification ships without type declarations
import { useToast } from 'vue-toastification';
import { ref } from 'vue';
import RegistryView from '../components/RegistryView.vue';
import MeasurementCard from './components/MeasurementCard.vue';
import {
  useMeasurement,
  useDeleteMeasurement,
  useMeasurementRetryFhir,
} from '@/bootstrap/measurement_api';
import type { MeasurementResponse } from '@/models/types';

const toast = useToast();
const emit = defineEmits(['register']);

const registryRef = ref<{ handleRefresh: () => Promise<void> }>();

const handleRegister = () => emit('register');

// Auto-polling kicks in while ANY measurement is still in-flight. We pick a
// generous predicate (pending + uploading) so a row that's just been created
// but not yet submitted still triggers polling — same posture workflow uses.
const hasPendingItem = (items: MeasurementResponse[]) =>
  items.some((m) => m.status === 'uploading' || m.status === 'pending');

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
</script>

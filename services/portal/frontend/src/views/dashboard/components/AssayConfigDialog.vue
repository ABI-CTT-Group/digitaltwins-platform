<template>
  <v-dialog v-model="open" width="auto" scrollable>
    <v-sheet class="config-sheet mx-auto" rounded="lg">
      <div class="config-sheet__head">
        <v-icon icon="mdi-cog-outline" color="#5fd6e8" size="34" class="mr-3" />
        <div>
          <h2 class="config-sheet__title">Configure assay "{{ assayName }}"</h2>
          <p class="config-sheet__sub">Set the workflow inputs, outputs, dataset and cohorts, then save.</p>
        </div>
      </div>

      <v-divider class="mb-2" />

      <div class="config-sheet__body">
        <AssayContent ref="assayContentRef" v-model="details" />
      </div>

      <v-divider class="mt-2 mb-4" />

      <div class="config-sheet__actions">
        <v-btn variant="text" class="text-none" @click="open = false">Cancel</v-btn>
        <v-btn color="#5fd6e8" variant="flat" class="text-none" :loading="saving" @click="onSave">Save</v-btn>
      </div>
    </v-sheet>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { storeToRefs } from "pinia";
import { useToast } from "vue-toastification";
import { useDashboardCacheStore } from "@/store/dashboard_cache_store";
import AssayContent from "@/components/domain/AssayContent.vue";

defineProps<{ assayName: string }>();
const open = defineModel<boolean>({ required: true });
const emit = defineEmits<{ (e: "save"): void }>();

const toast = useToast();
const { currentAssayDetails: details } = storeToRefs(useDashboardCacheStore());
const assayContentRef = ref<{ validate: () => Promise<boolean> }>();
const saving = ref(false);

const onSave = async () => {
  const valid = await assayContentRef.value?.validate();
  if (valid === false) {
    toast.warning("Please fill in all required fields before saving.");
    return;
  }
  saving.value = true;
  try {
    emit("save");
    open.value = false;
  } finally {
    saving.value = false;
  }
};
</script>

<style scoped>
.config-sheet {
  width: 80dvw;
  max-width: 1300px;
  padding: 26px 28px;
  background: rgba(8, 18, 26, 0.94) !important;
  border: 1px solid rgba(120, 200, 220, 0.18);
  color: #e9f2f5;
}
.config-sheet__head {
  display: flex;
  align-items: flex-start;
  margin-bottom: 16px;
}
.config-sheet__title {
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  font-size: 1.5rem;
  color: #fff;
}
.config-sheet__sub {
  margin: 4px 0 0;
  font-size: 0.88rem;
  color: #a4bac4;
}
.config-sheet__body {
  max-height: 62vh;
  overflow-y: auto;
}
.config-sheet__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>

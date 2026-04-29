<template>
  <div class="d-flex flex-column h-100 fill-height w-100 pb-5">
    <v-alert
      v-model="showAlert"
      close-label="Close Alert"
      color="red-lighten-1"
      icon="mdi-alert"
      :text="alertText"
      title="Oh no!"
      variant="tonal"
      closable
      class="w-100 mb-4"
    ></v-alert>

    <div class="h-100 flex-grow-1 overflow-y-auto">
      <slot name="content"></slot>
    </div>

    <div class="d-flex flex-row justify-center mt-4">
      <v-btn
        color="red"
        text="close"
        variant="tonal"
        :width="200"
        rounded="md"
        class="hover-animate ma-5"
        @click="$emit('close')"
      ></v-btn>
      <v-btn
        color="success"
        :text="submitBtnText"
        variant="tonal"
        :width="200"
        rounded="md"
        class="hover-animate ma-5"
        @click="$emit('submit')"
      ></v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';

const props = defineProps<{
  showError: boolean;
  errorText?: string;
  submitBtnText: string;
}>();

const emit = defineEmits(["close", "submit", "update:showError"]);

const showAlert = ref(props.showError);
const alertText = ref(props.errorText || "Some required fields are missing.");

watch(() => props.showError, (val) => {
  showAlert.value = val;
});

watch(showAlert, (val) => {
  emit("update:showError", val);
});
</script>

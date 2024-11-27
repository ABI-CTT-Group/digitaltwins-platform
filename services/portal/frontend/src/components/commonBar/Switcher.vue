<template>
  <div>
    <v-container>
      <v-row style="height: 60px">
        <v-col cols="7" class="d-flex justify-start align-center">
          {{ props.title }}
        </v-col>
        <v-col cols="5" class="d-flex justify-center align-center">
          <v-switch
            v-model="controller"
            color="switcher"
            :loading="loading"
            :disabled="disabled"
            :label="label"
            hide-details
            class="ml-5"
            @update:model-value="toggleUpdate"
          ></v-switch>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";

type Props = {
  title: string;
  controller: boolean;
  loading?: string | boolean;
  disabled?: boolean;
  label?: string;
};

// const controller = ref(false);

let props = withDefaults(defineProps<Props>(), {
  loading: false,
  disabled: false,
  controller: false,
  label: "off",
});
const emit = defineEmits(["toggleUpdate", "update:controller"]);

const controller = computed({
  get() {
    return props.controller;
  },
  set(val: boolean) {
    emit("update:controller", val);
  },
});

const toggleUpdate = (value: any) => {
  emit("toggleUpdate", value);
};
</script>

<style scoped></style>

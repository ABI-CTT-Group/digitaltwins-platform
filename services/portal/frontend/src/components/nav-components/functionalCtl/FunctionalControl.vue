<template>
    <v-progress-linear
        color="nav-success-2"
        buffer-value="0"
        stream
    ></v-progress-linear>
    <v-radio-group
        class="radio-group guide-operation-functional-control"
        v-model="commFuncRadio"
        label="Functional Controller"
        :inline="true"
        :disabled="disabled"
        @update:modelValue="toggleFuncRadios"
    >
        <v-radio
        v-for="(item, idx) in radioValues"
        :key="idx"
        :label="item.label"
        :value="item.value"
        :color="item.color"
        ></v-radio>
    </v-radio-group>
    <v-progress-linear
        color="nav-success-2"
        buffer-value="0"
        stream
    ></v-progress-linear>
</template>

<script setup lang="ts">
import { ref, computed  } from "vue";

type RadioValue = {
  label: string;
  value: string;
  color: string;
};

defineProps<{
  disabled: boolean,
  radioValues: RadioValue[],
}>();

const emit = defineEmits(["update:selectedRadio", "update:commFuncRadios"]);

const commFuncRadio = defineModel()

function toggleFuncRadios(value:any){
    emit("update:selectedRadio", value);
    commFuncRadio.value = value;
}

</script>

<style scoped>

</style>
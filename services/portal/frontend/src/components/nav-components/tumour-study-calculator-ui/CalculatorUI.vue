<template>
    <v-list-group value="Calculator">
      <template v-slot:activator="{ props }">
        <v-list-item
          v-bind="props"
          color="nav-success-2"
          prepend-icon="mdi-map-marker-distance"
          title="Calculate Distance"
        ></v-list-item>
      </template>
      <v-container fluid>
        <v-progress-linear
          color="nav-success-2"
          buffer-value="0"
          stream
        ></v-progress-linear>
        <v-radio-group
          class="radio-group"
          v-model="calculatorPickerRadios"
          label=""
          :inline="true"
          @update:modelValue="toggleCalculatorPickerRadios"
        >
      
        <v-radio
             v-for="(item, idx) in studyRadiosValue"
            :key="idx"
            :label="item.label"
            :value="item.value"
            :color="item.color"
            :disabled="item.disabled"
          ></v-radio>
        </v-radio-group>

        <v-select
          v-if="enableClockFace"
          class="mx-4"
          :items="clockFace"
          v-model="selectedClockFace"
          density="comfortable"
          label="Clock Face"
          variant="outlined"
          :disabled="clockFaceDisabled"
          @update:modelValue="onClockFaceChange"
        ></v-select>
        <v-btn
          class="ma-1"
          block
          density="comfortable"
          :disabled="finishBtnDisabled"
          @click="onFinishClick('finish')"
        >Finish</v-btn>
        <v-btn
          v-if="showNextBtn"
          color="pink"
          class="ma-1"
          block
          density="comfortable"
          @click="onNextCaseClick()"
        >{{ pinkBtnTitle }}</v-btn>
        <v-progress-linear
          color="nav-success-2"
          buffer-value="0"
          stream
        ></v-progress-linear>
      </v-container>
    </v-list-group>
</template>

<script setup lang="ts">
import { ref } from "vue";
const clockFace = ref(["12:00", "12:30", "1:00", "1:30", "2:00", "2:30", "3:00", "3:30", "4:00", "4:30", "5:00", "5:30", "6:00", "6:30", "7:00", "7:30", "8:00", "8:30", "9:00", "9:30", "10:00", "10:30", "11:00", "11:30", "central"]);

defineProps<{
  studyRadiosValue: {label: string, value: string, color: string, disabled: boolean}[],
  clockFaceDisabled: boolean,
  finishBtnDisabled: boolean,
  showNextBtn: boolean,
  pinkBtnTitle: string,
  enableClockFace: boolean
}>();

const calculatorPickerRadios = defineModel("radios");
const selectedClockFace = defineModel<string | null | undefined>("clockFace");

const emit = defineEmits(["update:selectedRadio", "update:selectedClockFace", "update:finishClick", "update:nextCaseClick"]);

function toggleCalculatorPickerRadios(value:any){
    emit("update:selectedRadio", value);
    calculatorPickerRadios.value = value;
}

function onClockFaceChange(value:any){
    emit("update:selectedClockFace", value);
    selectedClockFace.value = value;
}

function onFinishClick(value:any){
    emit("update:finishClick", value);
}

function onNextCaseClick(){
    emit("update:nextCaseClick");
}
</script>

<style scoped>

</style>
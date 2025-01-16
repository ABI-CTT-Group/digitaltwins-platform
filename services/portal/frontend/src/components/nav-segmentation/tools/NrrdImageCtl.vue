<template>
  <v-list-group value="Cases" class="guide-cases-overall">
    <template v-slot:activator="{ props }">
      <v-list-item
        v-bind="props"
        color="nav-success"
        prepend-icon="mdi-image"
        title="Cases Select"
      ></v-list-item>
    </template>

      <v-select
      class="mx-4"
      :items="allCasesDetails?.names"
      density="comfortable"
      label="Cases"
      variant="outlined"
      :autofocus="true"
      :disabled="disableSelectCase"
      @update:modelValue="onCaseSwitched"
    ></v-select>

    <v-select
      class="mx-4"
      v-model="slectedContrast"
      :items="contrastValue"
      :disabled="disableSelectContrast"
      chips
      label="Contrast Select"
      variant="outlined"
      multiple
      @update:modelValue="onContrastSelected"
    ></v-select>

    <Switcher
      v-model:controller="switchRegisted"
      :title="switchTitle"
      :disabled="switchDisabled"
      :label="switchLable"
      :loading="switchLoading"
      @toggleUpdate="toggleRegisterChanged"
      class="guide-case-switch"
    />
  </v-list-group>
</template>

<script setup lang="ts">
import Switcher from "@/components/commonBar/Switcher.vue";
import { ref, onMounted, onUnmounted } from "vue";
import { useSegmentationCasesStore } from "@/store/app";
import { storeToRefs } from "pinia";
import emitter from "@/plugins/custom-emitter";

type selecedType = {
  [key: string]: boolean;
};
type resultType = {
  [key: string]: any;
};

const { allCasesDetails } = storeToRefs(useSegmentationCasesStore());
const { getAllCasesDetails } = useSegmentationCasesStore();
const disableSelectCase = ref(false);
const disableSelectContrast = ref(true);
const contrastValue = ref<string[]>([]);
const slectedContrast = ref<string[]>([]);
const contrastOrder: any = {
  pre: 0,
  contrast1: 1,
  contrast2: 2,
  contrast3: 3,
  contrast4: 4,
};
const switchRegisted = ref<boolean>(true);
const switchTitle = ref<string>("Register Images");
const switchLoading = ref<boolean | string>(false);
const switchDisabled = ref<boolean>(true);
const switchLable = ref<"on" | "off">("on");

let contrastState: selecedType;

onMounted(() => {
  manageEmitters();
});


function manageEmitters() {
  emitter.on("Segmentation:FinishLoadAllCaseImages", emitterOnFinishLoadAllCaseImages);
  emitter.on("Segmentation:ContrastImageStates", emitterOnContrastImageStates);
}

const emitterOnFinishLoadAllCaseImages =  () => {
  disableSelectCase.value = false;
  switchDisabled.value = false;
  switchLoading.value = false;
}
const emitterOnContrastImageStates = (contrastStates:{[key:string]:boolean}) => {
  slectedContrast.value = [];
  contrastState = contrastStates as selecedType;
  contrastValue.value = Object.keys(contrastState);
  for (const key in contrastState) {
    if (contrastState.hasOwnProperty(key)) {
      if (contrastState[key]) {
        slectedContrast.value.push(key);
      }
    }
  }
  disableSelectContrast.value = false;
}

function onCaseSwitched(casename: any) {
  disableSelectCase.value = true;
  disableSelectContrast.value = true;
  switchDisabled.value = true;
  switchLable.value = "on";
  switchRegisted.value = true;
  switchLoading.value = "warning";
  emitter.emit("Segementation:CaseSwitched", casename);
}

function onContrastSelected(contrasts: string[]) {
  let result: resultType = {};
  sort(slectedContrast.value);
  for (const key in contrastState) {
    if (contrastState.hasOwnProperty(key)) {
      if (contrasts.includes(key)) {
        if (!contrastState[key]) {
          // add a contrast, set its state to ture
          contrastState[key] = true;
          result["effect"] = key;
          result["order"] = contrastOrder[key];
          result["contrastState"] = true;
          emitter.emit("Segmentation:ContrastChanged", result);
        }
      } else {
        if (contrastState[key]) {
          // remove a contrast, set its state to ture
          contrastState[key] = false;
          result["effect"] = key;
          result["order"] = contrastOrder[key];
          result["contrastState"] = false;
          emitter.emit("Segmentation:ContrastChanged", result);
        }
      }
    }
  }
}

function toggleRegisterChanged(value: boolean) {
  switchLable.value = switchLable.value === "on" ? "off" : "on";
  switchDisabled.value = true;
  switchLoading.value = "warning";
  emitter.emit("Segmentation:RegisterImageChanged", value);
}

const sort = (arr: string[]) => {
  arr.sort((a, b) => {
    return contrastOrder[a] - contrastOrder[b];
  });
};

onUnmounted(() => {
  emitter.off("Segmentation:FinishLoadAllCaseImages", emitterOnFinishLoadAllCaseImages);
  emitter.off("Segmentation:ContrastImageStates", emitterOnContrastImageStates);
});

</script>

<style scoped>
</style>

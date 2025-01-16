<template>
    <!-- Slider Controls -->
    <v-progress-linear
        color="nav-success"
        buffer-value="0"
        stream
    ></v-progress-linear>
    <v-radio-group
        class="radio-group guide-operation-slider-control"
        v-model="sliderRadio"
        label="Slider Controller"
        :inline="true"
        :disabled="disabled"
        @update:modelValue="toggleSliderRadios"
    >
        <v-radio
        v-for="(item, idx) in sliderRadioValues"
        :key="idx"
        :label="item.label"
        :value="item.value"
        :color="item.color"
        ></v-radio>
    </v-radio-group>
    <v-slider
        v-model="slider"
        :color="sliderColor"
        thumb-label="always"
        :disabled="sliderDisabled"
        :max="sliderMax"
        :min="sliderMin"
        :step="sliderStep"
        @update:modelValue="toggleSlider"
        @end="toggleSliderFinished"
    ></v-slider>
    <v-progress-linear
        color="nav-success"
        buffer-value="0"
        stream
    ></v-progress-linear>
</template>

<script setup lang="ts">
type RadioValue = {
  label: string;
  value: string;
  color: string;
};
defineProps<{
  sliderRadioValues: RadioValue[],
  disabled: boolean,
  sliderColor: string,
  sliderDisabled: boolean,
  sliderMax: number,
  sliderMin: number,
  sliderStep: number,
}>();

const sliderRadio = defineModel("sliderRadio");
const slider = defineModel<any>("slider");

const emit = defineEmits(["update:selectedSliderRadio", "update:slider", "update:sliderFinished"]);

function toggleSliderRadios(value:any){
    emit("update:selectedSliderRadio", value);
    sliderRadio.value = value;
}

function toggleSlider(value:any){
    emit("update:slider", value);
    slider.value = value;
}

function toggleSliderFinished(value:any){
    emit("update:sliderFinished", value);
}

</script>

<style scoped>

</style>
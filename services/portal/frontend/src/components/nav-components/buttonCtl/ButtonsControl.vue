<template>
    <!-- Buttons -->
    <v-progress-linear
        color="nav-success"
        buffer-value="0"
        stream
    ></v-progress-linear>

    <div class="guide-operation-comm-btns">
        <v-btn
            v-for="(btn, idx) in commFuncBtnValues"
            block
            density="comfortable"
            variant="outlined"
            class="my-1"
            :key="idx"
            :color="btn.color"
            :disabled="btn.disabled"
            @click="onBtnClick(btn.value)"
        >
            {{ btn.label }}
        </v-btn>
    </div>
    
    <v-progress-linear
        color="nav-success"
        buffer-value="0"
        stream
    ></v-progress-linear>
</template>

<script setup lang="ts">

defineProps<{
    commFuncBtnValues: {label: string, value: string, color: string, disabled: boolean}[]
}>();

const emit = defineEmits(["update:btnClicked"]);

function onBtnClick(value:string){
    emit("update:btnClicked", value);
}

</script>

<style scoped>

</style>
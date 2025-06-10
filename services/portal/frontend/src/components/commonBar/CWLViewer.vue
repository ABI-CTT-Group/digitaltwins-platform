<template>
    <vue-json-pretty :data="cwlData" />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import yaml from 'js-yaml'
import VueJsonPretty from 'vue-json-pretty'
import 'vue-json-pretty/lib/styles.css'

const props = defineProps<{
    cwlPath:string
}>()

const cwlData = ref({})

onMounted(async () => {
  const res = await fetch(props.cwlPath)
  const text = await res.text()
  cwlData.value = yaml.load(text)
})
</script>

<style scoped>

</style>
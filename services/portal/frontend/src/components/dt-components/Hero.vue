<template>
  <v-container class="text-center py-16 px-4 no-select" fluid>
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <h2 class="title gradient-animated font-weight-bold mb-4">
          {{ title }}
        </h2>
        <p class="text-white text-opacity-80 mb-8">
          {{ subtitle }}
        </p>
        <div class="d-flex justify-center flex-wrap gap-4">
         <slot></slot>
        </div>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts" setup>

defineProps({
  title: {
    type: String,
    default: 'Accelerating Development of Digital Twin and AI-Driven Workflows'
  },
  subtitle: {
    type: String,
    default: 'Seamlessly integrate digital twin and AI technologies into clinical and research environments'
  }
})


</script>

<style scoped>

.title{
    font-size: 3.5rem;
    line-height: 1.2;
}
.text-opacity-80 {
  opacity: 0.8;
}

.gap-4 {
  gap: 1rem;
}
.no-select{
    user-select: none;
  -webkit-user-select: none; /* Safari */
}
.gradient-animated{
  /* background: linear-gradient(90deg, #ff6b6b, #f8e71c, #50e3c2, #7c4dff); */
  background: linear-gradient(90deg, #1fb7d9, #ffffff, #1fb7d9);
  background-size: 300% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
  animation: slide-gradient 20s linear infinite;
}

@keyframes slide-gradient {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
</style>

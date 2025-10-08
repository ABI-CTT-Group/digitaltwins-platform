<template>
  
  <v-card
    class="tech-card neon-border"
    elevation="12"
    :width="width || 400"
  >
    <v-card-title class="text-center title font-weight-bold text-blue-lighten-2">
      {{ title }}
    </v-card-title>

    <v-divider class="my-2 border-blue-accent-2"></v-divider>

    <v-card-text v-if="!!description" class="text-blue-grey-lighten-4 d-flex align-center justify-center" :style="`min-height: ${height || 100}px;`">
      <div class="text-blue-lighten-2">{{ description }}</div>
    </v-card-text>

    <v-divider v-if="!!description" class="my-2 border-blue-accent-2"></v-divider>

    <v-card-actions class="justify-center">
      <v-btn
        variant="outlined"
        rounded="md"
        color="blue-accent-2"
        class="glow-btn mb-2"
        @click="handleBtnClick"
      >
        Explore More
      </v-btn>
    </v-card-actions>
  </v-card>

</template>
<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router';
import { onMounted } from 'vue';
const router = useRouter();

const props = defineProps<{
    herf:string,
    title:string,
    description?:string,
    width?:number,
    height?:number
}>()

const handleBtnClick = ()=>{
  if(props.herf.startsWith("http")){
    window.open(props.herf, '_blank');
  }else{
    router.push({name:props.herf})
  } 
}

</script>

<style scoped>
.title {
  font-size: 1.1rem;
  font-weight: 300;
}
.tech-card {
  position: relative;
  background: rgba(20, 30, 60, 0.4);
  backdrop-filter: blur(14px);
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(0, 200, 255, 0.3);
  box-shadow: 0 0 20px rgba(0, 200, 255, 0.1);
  transition: all 0.3s ease;
}

.tech-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 0 30px rgba(0, 200, 255, 0.3);
}

.neon-border::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 2px;
  background: linear-gradient(120deg, 
    #00eaff 0%, 
    #0055ff 25%, 
    #00eaff 50%, 
    #0055ff 75%, 
    #00eaff 100%);
  background-size: 300% 300%;
  animation: borderFlow 4s linear infinite;
  -webkit-mask: 
    linear-gradient(#fff 0 0) content-box, 
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
}

@keyframes borderFlow {
  0% { background-position: 0% 50%; }
  100% { background-position: 300% 50%; }
}

.glow-btn {
  font-size: 0.7rem;
  border: 1px solid rgba(0, 200, 255, 0.6);
  box-shadow: 0 0 10px rgba(0, 200, 255, 0.2);
  transition: all 0.3s ease;
}

.glow-btn:hover {
  box-shadow: 0 0 20px rgba(0, 200, 255, 0.5);
  background: rgba(0, 200, 255, 0.15);
}
</style>
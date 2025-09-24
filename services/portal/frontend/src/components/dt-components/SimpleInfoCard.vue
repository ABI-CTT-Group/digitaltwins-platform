<template>
    <v-card
        class="mx-auto card-color"
      >
        <v-card-item>
          <div>
            <div class="text-overline mb-1">
              {{ category }}
            </div>
            <div class="text-h6 mb-1 text-grey-lighten-3 title">
              {{ title }}
            </div>
            <div class="text-caption text-grey-lighten-2">{{ description }}</div>
          </div>
        </v-card-item>

        <v-card-actions>
          <v-btn 
            color="#bfdbfe"
            class="w-100"
            append-icon="mdi-open-in-new"
            variant="tonal"
            @click="handleBtnClick">
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
    category:string,
    herf:string,
    title:string,
    description:string
}>()

const handleBtnClick = ()=>{
  if(props.herf.startsWith("http")){
    window.open(props.herf, '_blank');
  }else{
    router.push({name:props.herf})
  } 
}

onMounted(()=>{
  console.log(props.description);
  
})
</script>

<style scoped>
.container{
    min-height: 4rem;
}
.title{
  min-height: 4rem;
}
.card-color {
    background: linear-gradient(to bottom, rgba(255,255,255,0.35) 0%, rgba(0,0,0,0.35) 100%), radial-gradient(at top center, rgba(255,255,255,0.60) 0%, rgba(0,0,0,0.60) 120%) #989898; background-blend-mode: multiply,multiply;
    background-color: transparent !important;
}
</style>
<template>
    <v-card
        color="#bfdbfe"
        variant="outlined"
        class="mx-auto"
      >
        <v-card-item>
          <div>
            <div class="text-overline mb-1">
              {{ category }}
            </div>
            <div class="text-h6 mb-1 text-grey-lighten-3">
              {{ title }}
            </div>
            <div class="text-caption text-grey-lighten-2 container">{{ description }}</div>
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

  } 
}
</script>

<style scoped>
.container{
    min-height: 4rem;
}
</style>
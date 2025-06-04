<template>
     <!-- <v-card
        append-icon="mdi-open-in-new"
        class="container mx-auto"
        :href="herf"
        max-width="344"
        prepend-icon="mdi-github"
        rel="noopener"
        subtitle="Check out the official repository"
        target="_blank"
        title="Vuetify on GitHub"
    ></v-card> -->
    <v-card
        color="#bfdbfe"
        variant="outlined"
        class="mx-auto"
      >
        <v-card-item>
          <div>
            <div class="text-overline mb-1">
              Tutorial
            </div>
            <div class="text-h6 mb-1 text-grey-lighten-3">
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

const props = defineProps<{
    herf:string,
    title:string,
    description:string
}>()

const handleBtnClick = ()=>{
    window.open(props.herf, '_blank');
}
</script>

<style scoped>
.container{
    background-color: oklch(44.6% 0.043 257.281);
}
</style>
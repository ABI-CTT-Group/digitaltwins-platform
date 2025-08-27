<template>
  <v-container class="text-center py-16 px-4 no-select" fluid>
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <h2 class="title font-weight-bold mb-4">
          Enabling AI-Driven Clinical Workflows
        </h2>
        <p class="text-white text-opacity-80 mb-8">
          Seamlessly integrate digital twin technologies into clinical and research environments.
        </p>
        <div class="d-flex justify-center flex-wrap gap-4">
          <v-btn
            color="green-lighten-2"
            class="text-sky-900 px-6 py-3"
            size="large"
            elevation="6"
            rounded="xl"
            variant="tonal"
            @click="handleHeroStartClick"
          >
            Get Started
          </v-btn>
          <v-btn
            color="purple-lighten-2"
            class="text-white px-6 py-3"
            size="large"
            elevation="6"
            rounded="xl"
            variant="tonal"
            @click="handleHeroDocumentationClick"
          >
            Documentation
          </v-btn>
        </div>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts" setup>

const emit = defineEmits(["started", "documentation"])

const handleHeroStartClick = () => {
    emit('started')
}

const handleHeroDocumentationClick = ()=>{
    emit('documentation')
}

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
</style>

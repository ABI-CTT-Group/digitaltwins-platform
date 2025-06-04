<template>
    <div class="container w-screen h-screen d-flex flex-column align-center">
        <div class="d-flex flex-column w-100 ma-5">
            <h1 class="mx-auto">Tutorial</h1>
            <v-divider></v-divider>
        </div>
        <div class="main-container d-flex justify-center align-center pa-1">
            <div>
                <v-row justify="center">
                    <v-col
                        v-for="(variant, i) in [1,2,3,4]"
                        :key="i"
                        cols="12"
                        md="3"
                    >
                        <TutorialCard 
                            herf="https://colab.research.google.com/drive/15c_v9sK4wSF3Rng3j6xk-L6ngfWEEbPq" 
                            title="DigitalTWINS on FHIR" 
                            description="DigitalTWINs on FHIR uses FHIR R4 to integrate EHR and research data via a structured specification."/>
                    </v-col>
                </v-row>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import TutorialCard from './components/TutorialCard.vue';

</script>

<style scoped>
.container{
  /* background: #556270;   */
  background: oklch(70.5% 0.015 286.067);
}
.main-container{
    flex: 1;
    width: 80%;
}
</style>
<template>
    <div class="container w-screen h-screen d-flex flex-column align-center overflow-hidden">
        <NavHome>
            <h1 class="mx-auto">Catalogue Dashboard</h1>
        </NavHome>
        <div class="main-container overflow-y-auto d-flex align-center">
            <v-row justify="center">
                <v-col
                    cols="12"
                    md="6"
                >
                    <SimpleInfoCard
                        category="Seek"
                        herf="http://130.216.217.147:3000/"
                        title="Edit in Seek website"
                        description="Programmes, Projects, Investigations, Studies, Assays, Measurements, Models"
                    />
                </v-col>
                <v-col
                    cols="12"
                    md="6"
                >
                    <SimpleInfoCard
                        category="Catalogue dashboard"
                        herf="Home"
                        title="Edit in Catalogue dashboard"
                        description="Workflows, Tools​"
                    />
                </v-col>
            </v-row>
        </div>
    </div>
</template>

<script setup lang="ts">
import NavHome from '@/views/dashboard/components/NavHome.vue';
import SimpleInfoCard from '@/views/dashboard/components/SimpleInfoCard.vue';

</script>

<style scoped>
.container{
  background: #556270;  
  background: -webkit-linear-gradient(to right, #FF6B6B, #556270);  
  background: linear-gradient(to right, #FF6B6B, #556270); 
}
.main-container{
    width: 80%;
    padding-top: 100px;
    height: 95%;
}
</style>
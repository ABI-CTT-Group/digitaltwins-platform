<template>
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
                herf="WorkflowToolsViewer"
                title="Edit in Catalogue dashboard"
                description="Workflows, Tools​"
            />
        </v-col>
    </v-row>
    
</template>

<script setup lang="ts">
import SimpleInfoCard from '@/views/dashboard/components/SimpleInfoCard.vue';
</script>

<style scoped>

</style>
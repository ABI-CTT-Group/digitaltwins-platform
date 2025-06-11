<template>
    <v-row justify="center">
        <v-col
            cols="12"
            md="6"
        >
            <SimpleInfoCard
                category="Seek"
                herf="http://130.216.217.147:3000/"
                title="Programmes, Projects, Investigations, Studies, Assays, Measurements, Models"
                description=""
            />
        </v-col>
        <v-col
            cols="12"
            md="6"
        >
            <SimpleInfoCard
                category="DigitalTWINS Platform"
                herf="WorkflowToolsViewer"
                title="Workflows, Tools"
                description="​"
            />
        </v-col>
    </v-row>
    
</template>

<script setup lang="ts">
import SimpleInfoCard from '@/views/dashboard/components/SimpleInfoCard.vue';
</script>

<style scoped>

</style>
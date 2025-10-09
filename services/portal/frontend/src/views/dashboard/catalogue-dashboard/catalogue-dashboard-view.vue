<template>
<div class="layout d-flex flex-column align-center">
    <div >
      <SimpleInfoCard
            :herf="cards[0].herf"
            :title="cards[0].title"
            :description="cards[0].description"
        />
    </div>

    <v-row
      class="d-flex justify-center align-center flex-wrap mt-8 sub-card-row"
      no-gutters
    >
      <div
        v-for="(card, i) in cards.slice(1)"
        :key="i"
        class="tech-card neon-border mx-8 my-6"
      >
        <SimpleInfoCard
            :herf="card!.herf"
            :title="card!.title"
            :description="card!.description"
        />
      </div>
    </v-row>
</div>
</template>

<script setup lang="ts">
import SimpleInfoCard from '@/components/dt-components/SimpleInfoCard.vue';
import { ref, computed } from 'vue';

const cards =[
    {
        title: 'SEEK Catalogue',
        description: 'View or create descriptions for programmes, projects, investigations, studies, assays, and view existing workflows and tools.',
        herf: 'http://130.216.216.26:8001/'
    },
    {
        title: 'Upload workflow tool',
        description: 'Upload a new workflow tool to the platform.',
        herf: 'UploadToolDataset'
    },
    {
        title: 'Upload workflow',
        description: 'Upload a new workflow to the platform.',
        herf: '#'
    },
     {
        title: 'Workflow assembler',
        description: 'Assemble & and uploading a new workflow to the platform.',
        herf: 'WorkflowToolsViewer'
    }
];

</script>

<style scoped>
.layout {
    width: 100%;
    padding-top: 100px;
}
</style>
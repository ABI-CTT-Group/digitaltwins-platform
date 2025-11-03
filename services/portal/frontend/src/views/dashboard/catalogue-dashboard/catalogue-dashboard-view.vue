<template>
<div class="layout overflow-y-auto d-flex flex-column align-center justify-center ">

  <div class="d-flex justify-center align-center mb-12">
    <SimpleInfoCard
      :herf="cards[0].herf"
      :title="cards[0].title"
      :description="cards[0].description"
    />
  </div>

  <div
    class="d-flex justify-center align-center flex-wrap sub-card-row"
    style="gap: 2rem;"  
  >
    <div
      v-for="(card, i) in cards.slice(1)"
      :key="i"
      class="d-flex justify-center"
    >
      <SimpleInfoCard
        :herf="card.herf"
        :title="card.title"
        :description="card.description"
      />
    </div>
  </div>
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
        herf: 'UploadWorkflowDataset'
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
    height: 100%;
    padding-top: 100px;
}
.sub-card-row {
  gap: 1.5rem;
}

@media (max-width: 960px) {
  .sub-card-row {
    gap: 1rem;
  }
}

</style>
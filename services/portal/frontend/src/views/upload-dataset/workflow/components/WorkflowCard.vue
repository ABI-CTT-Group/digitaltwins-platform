<template>
    <CardUI 
      cardStyle="background: rgba(255, 153, 0, 0.03);"
      :isDeleting="isDeleting"
      v-model:menu="menu"
    >
      <template #menu>
          <v-list density="compact" class="py-0 cursor-pointer">
              <v-list-item density="compact" @click.stop="onSubmit">
                  <v-list-item-title class="hover-animate px-2">Submit to Approval</v-list-item-title>
              </v-list-item>
              <v-list-item density="compact" @click.stop="onDelete" color="red">
                  <v-list-item-title class="text-red hover-animate px-2">Delete Workflow</v-list-item-title>
              </v-list-item>
          </v-list>
      </template>
      <template #name>{{ workflow.name }}</template>
      <template #description>{{ workflow.description }}</template>
      <template #tags>
          <v-chip v-if="!!workflow.version" size="small" color="blue-lighten-4" text-color="blue-darken-3" class="mx-1 my-1">v{{ workflow.version }}</v-chip>
          <v-chip v-if="!!workflow.author" size="small" color="blue-lighten-5" text-color="blue-darken-3" class="mx-1 my-1">{{ workflow.author }}</v-chip>
          <v-chip v-if="!!workflow.status" size="small" :color="statusColor" :text-color="statusTextColor" class="mx-1 mr-1 my-1">{{ workflow.status }}</v-chip>
      </template>
      <template #time>
          <v-chip v-if="!!workflow.created_at" size="small" color="green-lighten-4" text-color="green-darken-2" class="ms-auto">{{ formatDate(workflow.created_at) }}</v-chip>
      </template>
      
    </CardUI>
</template>

<script setup lang="ts">
import { computed, ref, watch, toRef } from 'vue'
import { IWrokflowResponse } from '@/models/uiTypes';
import CardUI from '../../components/CardUI.vue';
import { formatDate } from '../../components/utils';

const props = defineProps<{
  workflow: IWrokflowResponse
}>()

const menu = ref(false);
const workflow = toRef(props, "workflow")
const isDeleting = ref(false)


const emit = defineEmits(["submit-approve",  "delete"])

const statusColor = computed(() => {
  switch (props.workflow.status) {
    case "pending":
      return "amber-lighten-2"
    case "building":
      return "blue-lighten-2"
    case "failed":
      return "red-lighten-2"
    case "completed":
      return "green-lighten-2"
    default:
      return ""
  }
})

const statusTextColor = computed(() => {
  switch (props.workflow.status) {
    case "pending":
      return "amber-darken-3"
    case "building":
      return "blue-darken-3"
    case "failed":
      return "red-darken-3"
    case "completed":
      return "green-darken-3"
    default:
      return ""
  }
})

const onSubmit = () => {
    menu.value = false;
    emit("submit-approve", workflow.value.id)
}

const onDelete = () => {
    menu.value = false;
    isDeleting.value = true;
    emit("delete", workflow.value.id)
}
</script>

<style scoped>
.title {
    font-size: large;
}

.subtitle{
    font-size: small;
    line-height: 1.5em;         
    max-height: 4em;             
    overflow: hidden;
    display: -webkit-box;
    box-orient: vertical;
    -webkit-box-orient: vertical;
    line-clamp: 2;
    -webkit-line-clamp: 2;        
    text-overflow: ellipsis; 
}
.card-hover-animate {
  transition: all 0.3s ease;
  transform: scale(1);
}
.card-hover-animate:hover {
  transform: scale(1.02) !important;
}
.shadow-card {
    background: rgba(255, 153, 0, 0.15);
    border-radius: 10px !important;
    box-shadow:
        0 0 10px rgba(255, 153, 0, 0.6),
        0 0 10px rgba(255, 153, 0, 0.5),
        inset 0 0 10px rgba(255, 153, 0, 0.3) !important;
}


</style>
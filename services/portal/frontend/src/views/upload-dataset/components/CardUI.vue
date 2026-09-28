
<template>
    <v-card 
        class="pa-4 shadow-card card-hover-animate" 
        width="400"
        max-height="230" 
        rounded="lg" 
        elevation="2"
        :disabled="isDeleting"
        :loading="isDeleting"
        :style="cardStyle" >
        <div class="d-flex justify-space-between align-start">
          <v-avatar
              size="36px"
              >
              <v-icon
                  color="yellow"
                  icon="mdi-tag"
              ></v-icon>
          </v-avatar>

          <div class="d-flex align-center">
              <slot name="launch"></slot>
              <v-menu v-model="menu" location="bottom end">
                  <template #activator="{ props }">
                      <div class="hover-animate cursor-pointer border-md rounded pa-1">
                          <v-icon
                              v-bind="props"
                              icon="mdi-dots-vertical"
                              color="grey"
                              size="small"
                              class="hover-animate"
                          ></v-icon>
                      </div>
                      
                  </template>

                  <slot name="menu"></slot>
              </v-menu>
          </div>
        
        </div>

        <div class="mt-3">
        <div class="font-weight-bold title">
            <slot name="name"></slot>
        </div>
        <div class="subtitle py-3">
            <slot name="description"></slot>
        </div>
        </div>

        <div class="d-flex flex-wrap align-center mt-4 gap-2">
          <div class="d-flex flex-wrap align-center w-75">
              <slot name="tags"></slot>
          </div>
             <slot name="time"></slot>
        </div>
    </v-card>
</template>

<script lang="ts" setup>

const props = withDefaults(
  defineProps<{
    isDeleting?: boolean
    cardStyle?: string
  }>(),
  {
    isDeleting: false,
    cardStyle: "",
  }
)

const menu = defineModel('menu', { type: Boolean, default: false });
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
</style>
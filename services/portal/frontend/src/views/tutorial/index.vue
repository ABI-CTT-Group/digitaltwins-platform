<template>
    <div class="container w-screen h-screen d-flex flex-column align-center overflow-hidden">
        <div class="main-container overflow-y-auto">
             <div class="my-2">
                <h3 class="mb-2">About</h3>
                <v-divider thickness="5"></v-divider>
                <div class="help-list py-3 d-flex flex-wrap justify-start">
                    
                </div>
            </div>

            <div v-for="(section, i) in sections" :key="i" class="my-2">
                <h3 class="mb-2">{{ section.title }}</h3>
                <v-divider thickness="5"></v-divider>
                <div class="help-list py-3 d-flex flex-wrap justify-start">
                    <SimpleInfoCard 
                        v-for="(item, j) in section.items"
                        :key="j"
                        class="mx-2"
                        :herf="item.herf"
                        :title="item.title"
                        :width="item.width"
                    />
                </div>
            </div>
            
        </div>
    </div>
</template>

<script setup lang="ts">
import SimpleInfoCard from '@/components/domain/SimpleInfoCard.vue';
import { sections } from './tutorial.config';
</script>

<style scoped>
.main-container{
    width: 80%;
    margin-top: 100px;
    margin-bottom: 20px;
    padding: 50px;
    height: 90%;
    background: rgba(1, 62, 62, 0.15); 
    border-radius: 10px !important;
    box-shadow:  5px 5px 10px #071b25,
             -5px -5px 10px #0d3547 !important;
}
</style>
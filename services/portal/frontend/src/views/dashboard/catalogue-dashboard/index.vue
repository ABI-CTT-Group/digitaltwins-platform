<template>
    <div class="container w-screen h-screen d-flex flex-column align-center overflow-hidden">
        <div class="main-container overflow-y-auto d-flex align-center">
            <router-view/>
        </div>
    </div>
</template>

<script setup lang="ts">

</script>

<style scoped>
.main-container{
    width: 80%;
    padding-top: 100px;
    height: 95%;
}
</style>
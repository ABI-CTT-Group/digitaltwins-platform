<template>
    <div class="logo d-flex justify-space-between align-center ">
        
        <div class="d-flex align-center cursor-pointer pa-2 home-icon"
            @click="handleHomeClick"
        >
            <v-icon
                color="blue-darken-2"
                class="mr-2"
                icon="mdi-home-outline"
                size="large"
            ></v-icon>
            <h3>
                DigitalTWINS AI Platform 
            </h3>
            <!-- 
            <span class="mt-1 ml-2">
                Home
            </span> -->
        </div>
        
        <div class="my-font">
            <slot></slot>
        </div>

        <div class="logo-img-div">
            <img src="@/assets/images/abi.png" alt="" />
        </div>
    </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

const router = useRouter();
const handleHomeClick = ()=>{
    router.push({name:"Home"});
}

</script>

<style scoped>
.logo{
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 70px;
    border-bottom-left-radius: 3px;
    border-bottom-right-radius: 3px;
    padding: 0 20px;
    background: rgba(255, 255, 255, 0.2); 
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2); 
    backdrop-filter: blur(10px); 
    -webkit-backdrop-filter: blur(10px);
    z-index: 1000;
}
.home-icon:hover{
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 10px;

}
.logo-img-div{
    width: 11vw;
    height: 2.1vw;
}
.logo-img-div img{
    width: 100%;
    height: 100%;
}
.my-font{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 
               "PingFang SC", "Noto Sans", "Microsoft YaHei", sans-serif;
    user-select: none;
}
</style>
<template>
    <div class="d-flex justify-center align-center h-screen content">
        <div class="glass pa-10">
            <LoginPage />
        </div>
    </div>
</template>

<script setup lang="ts">
import LoginPage from './login/index.vue'
</script>

<style scoped>
.content {
    background-image: url("@/assets/login_bg.jpg"); 
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
}
.glass {
  background: rgba(255, 255, 255, 0.15); 
  border-radius: 15px;
  backdrop-filter: blur(15px); 
  -webkit-backdrop-filter: blur(15px); 
  border: 1px solid rgba(255, 255, 255, 0.3); 
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
  display: flex;
  justify-content: center;
  align-items: center;
  color: white;
  font-size: 18px;
  font-weight: bold;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2); /* 让文字清晰一点 */
}
</style>
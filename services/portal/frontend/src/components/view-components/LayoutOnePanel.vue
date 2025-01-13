<template>
    <div class="main-container " ref="mainContainer">
      <div
        class="box bg-grey-darken-4 ml-1 rounded-lg"
      >
        <slot></slot>
      </div>
    </div>
  </template>
  
  <script lang="ts" setup>
  
  </script>
  
  <style scoped>
  .main-container {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
    padding: 0.3rem;
    overflow: hidden;
    position: relative;
    user-select: none;
    -webkit-user-select: none;
  }
  .box {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
  }
  </style>
  
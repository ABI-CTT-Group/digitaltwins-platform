<template>
  <v-navigation-drawer
    v-model="drawer"
    :rounded="true"
    :disable-resize-watcher="true"
    :width="350"
    :permanent="!temporary"
    :temporary="temporary"
  >
    <slot></slot>
  </v-navigation-drawer>

  <v-app-bar color="surface" class="d-flex justify-end">

    <v-app-bar-nav-icon class="guide-bar-nav" @click="toggleDrawer"></v-app-bar-nav-icon>

    <div class="guide-expand-panel" data-tool="expandtool"></div>
    <v-app-bar-title >
      <span class="text-capitalize"
        >
        {{ title }}
      </span>
      <span class="text-body-2 font-italic text-deep-orange mx-2">
        {{ version }}
      </span>
    </v-app-bar-title>

    <div width="" class="w-50 d-flex flex-row justify-end align-center px-2">
      <IntroPanel />
       <slot name="theme"></slot>
      <v-img
        class="px-5"
        width="250px"
        max-width="250px"
        src="@/assets/images/abi.png"
      ></v-img>
    </div>
  </v-app-bar>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import IntroPanel from "@/components/intro/IntroPanel.vue";
import emitter from "@/plugins/custom-emitter";;


defineProps({
  title: {
    type: String,
    default: "Tumour Position & Extent Reporting App",
  },
  version: {
    type: String,
    default: "v3.0.0",
  },
});

const drawer = ref(false);
const temporary = ref(true);


onMounted(() => {
  manageEmitters();
});

function manageEmitters() {
  // set_nav_sticky_mode
  emitter.on("Common:NavStickyMode", emitterOnNavStickyMode);
  emitter.on("IntroGuide:DrawerStatus", emitterOnDrawerStatus);
}

const emitterOnNavStickyMode = (val:boolean) => {
  temporary.value = !val;
  emitter.emit("Common:ResizeCopperSceneWhenNavChanged", {
    panel: "right",
  });
}
const emitterOnDrawerStatus = (val:string)=>{
  if(val==="open" && !drawer.value){
    toggleDrawer();
  }
}

function toggleDrawer() {
  drawer.value = !drawer.value;
  temporary.value = !drawer.value;

  emitter.emit("Common:DrawerStatus", drawer.value);
  emitter.emit("Common:NavStickyMode", drawer.value);
  emitter.emit("Common:ResizeCopperSceneWhenNavChanged", {
    panel: "right",
  });
}

onUnmounted(() => {
  emitter.off("Common:NavStickyMode", emitterOnNavStickyMode);
  emitter.off("IntroGuide:DrawerStatus", emitterOnDrawerStatus);
});

</script>
<style></style>

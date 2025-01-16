<template>
  <v-app>
    <default-bar> 
      <NavPanel />
      <template #theme>
        <v-btn
          color="secondary-font"
          class="px-5"
          density="compact"
          icon="mdi-theme-light-dark"
          @click="toggleTheme"
        ></v-btn>
      </template>
    </default-bar>

    <default-view />
  </v-app>
</template>

<script lang="ts" setup>
import DefaultBar from "../components/AppBar.vue";
import DefaultView from "./View.vue";
import NavPanel from "@/components/nav-segmentation/NavPanel.vue";
import { useTheme } from "vuetify";
import { ref } from "vue";
import emitter from "@/plugins/custom-emitter";;

const theme = useTheme();
const drawerTheme = ref("dark");

function toggleTheme(value: any) {
  // theme.global.current.value.dark
  theme.global.name.value = theme.global.current.value.dark
    ? "lightTheme"
    : "darkTheme";

  drawerTheme.value = theme.global.current.value.dark ? "dark" : "light";

  emitter.emit("Common:ToggleAppTheme", theme.global.name.value);
}
</script>

<style></style>

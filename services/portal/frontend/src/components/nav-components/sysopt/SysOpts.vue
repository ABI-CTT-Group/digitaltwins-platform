<template>
  <v-list-group value="Opts">
    <template v-slot:activator="{ props }">
      <v-list-item
        v-bind="props"
        color="primary"
        prepend-icon="mdi-cogs"
        title="Opts"
      ></v-list-item>
    </template>

    <slot></slot>
  </v-list-group>
</template>

<script setup lang="ts">

</script>

<style scoped></style>

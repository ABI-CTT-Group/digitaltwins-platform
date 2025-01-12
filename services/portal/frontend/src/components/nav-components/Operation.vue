<template>
  <v-list-group value="Operation" class="guide-operation-overall" data-tool="operationtool">
        <template v-slot:activator="{ props }">
            <v-list-item
                v-bind="props"
                color="nav-success"
                prepend-icon="mdi-axe"
                title="Operation Settings"
            ></v-list-item>
        </template>
        <!-- Calculator Control -->
        <slot name="Calculator"></slot>
        <!-- Functional Control -->
        <v-container fluid>
            <slot name="FunctionalControl"></slot>
            <slot name="SliderControl"></slot>
            <slot name="ButtonControl"></slot>
        </v-container>
        <slot name="OperationAdvance"></slot>
    </v-list-group>
</template>

<script setup lang="ts">

</script>

<style>
.v-selection-control-group--inline {
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: space-between;
  padding: 0 10px;
}
</style>
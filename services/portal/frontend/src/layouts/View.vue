<template>
  <v-main>
    <div ref="scroller" class="page-scroll">
      <router-view />
    </div>
  </v-main>
</template>

<script lang="ts" setup>
import { ref, watch, nextTick } from "vue";
import { useRoute } from "vue-router";

// .page-scroll is a single persistent scroll container shared across routes,
// so its scrollTop survives navigation. Reset it to the top on every route
// change so a new page never inherits the previous page's scroll position.
const scroller = ref<HTMLElement | null>(null);
const route = useRoute();

watch(
  () => route.fullPath,
  () => {
    nextTick(() => {
      if (scroller.value) scroller.value.scrollTop = 0;
    });
  }
);
</script>

<style scoped>
/* v-main itself does NOT scroll — the inner .page-scroll does. Flex column so
   .page-scroll reliably fills the area BELOW the app-bar (v-main's padding-top)
   without depending on percentage-height + padding math. */
.v-main {
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* The scroll container. Its top edge sits at the navbar's bottom and overflow
   clips there — so page content scrolls BELOW the glass navbar and never slides
   under it. That keeps the navbar's backdrop-filter cheap (static aurora behind
   it, no per-frame re-blur on scroll). Restores the behaviour the global
   `.container { height:100dvh }` rule used to provide, without that rule. */
.page-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}
</style>

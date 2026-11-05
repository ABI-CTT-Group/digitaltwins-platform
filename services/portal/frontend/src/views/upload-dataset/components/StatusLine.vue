<template>
  <div class="status" :class="`status--${status.tone}`">
    <span class="status__mark" aria-hidden="true"></span>
    <div class="status__text">
      <p class="status__sentence">{{ status.sentence }}</p>
      <p v-if="detail" class="status__detail" :title="status.reason">{{ detail }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { CardStatus } from './cardStatus';

const props = defineProps<{ status: CardStatus }>();

// A failure's reason wins over the hint: it says what to fix.
const detail = computed(() => props.status.reason || props.status.hint);
</script>

<style scoped>
/* The one bold element on a card. Quiet when fine, loud when not: steady states keep the text colour,
   running is pale with a slow shimmer on the mark, needs-you is amber, failed is coral. */
.status {
  --tone: var(--text-dim);
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.status--running { --tone: var(--text); }
.status--needs { --tone: var(--tone-needs); }
.status--failed { --tone: var(--tone-failed); }

.status__mark {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  margin-top: 0.45em;
  border-radius: 50%;
  background: var(--tone);
}
.status--running .status__mark { animation: status-pulse 1.8s ease-in-out infinite; }
@keyframes status-pulse { 50% { opacity: 0.3; } }
@media (prefers-reduced-motion: reduce) {
  .status--running .status__mark { animation: none; }
}

.status__text { min-width: 0; }
.status__sentence {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  line-height: 1.35;
  color: var(--text);
}
.status--needs .status__sentence,
.status--failed .status__sentence { color: var(--tone); }
.status--running .status__sentence { color: var(--text-dim); }
.status__detail {
  margin: 2px 0 0;
  font-size: 0.8125rem;
  line-height: 1.45;
  color: var(--text-dim);
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>

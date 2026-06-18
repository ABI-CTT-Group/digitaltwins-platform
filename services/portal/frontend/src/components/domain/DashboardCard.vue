<template>
  <button type="button" class="dcard" @click="$emit('on-explore', title)">
    <span class="dcard__cover">
      <v-img :src="src" height="148" cover></v-img>
      <span v-if="external" class="dcard__badge" title="Opens in a new tab">↗</span>
      <span v-else-if="locked" class="dcard__badge" title="Role-restricted"><v-icon icon="mdi-lock-outline" size="13" /></span>
    </span>
    <span class="dcard__body">
      <span class="dcard__title">{{ title }}</span>
      <span class="dcard__loc">{{ location }}<template v-if="external"> · external</template></span>
      <v-tooltip :text="description" location="bottom" open-delay="300" :disabled="!description">
        <template #activator="{ props: td }">
          <span class="dcard__desc" v-bind="td">{{ description }}</span>
        </template>
      </v-tooltip>
    </span>
  </button>
</template>

<script setup lang="ts">
defineProps<{
  src?: string;
  title?: string;
  location?: string;
  description?: string;
  external?: boolean;
  locked?: boolean;
}>();
defineEmits<{ (e: 'on-explore', title?: string): void }>();
</script>

<style scoped>
.dcard {
  display: flex;
  flex-direction: column;
  width: 100%;
  text-align: left;
  cursor: pointer;
  border-radius: 16px;
  border: 1px solid rgba(120, 200, 220, 0.16);
  background: rgba(255, 255, 255, 0.03);
  overflow: hidden;
  font-family: "Nunito", sans-serif;
  color: inherit;
  transition: transform 0.4s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.4s ease, background 0.4s ease, box-shadow 0.4s ease;
}
.dcard:hover {
  transform: translateY(-4px);
  border-color: rgba(95, 214, 232, 0.4);
  background: rgba(255, 255, 255, 0.05);
  box-shadow: 0 16px 36px -14px rgba(0, 0, 0, 0.55), 0 0 26px -8px rgba(95, 214, 232, 0.3);
}
.dcard__cover { position: relative; display: block; overflow: hidden; }
/* subtle cover zoom on hover */
.dcard__cover :deep(.v-img__img) { transition: transform 0.55s cubic-bezier(0.22, 1, 0.36, 1); }
.dcard:hover .dcard__cover :deep(.v-img__img) { transform: scale(1.06); }
@media (prefers-reduced-motion: reduce) {
  .dcard, .dcard__cover :deep(.v-img__img) { transition: none; }
  .dcard:hover { transform: none; }
  .dcard:hover .dcard__cover :deep(.v-img__img) { transform: none; }
}
.dcard__badge {
  position: absolute;
  top: 8px;
  right: 8px;
  display: grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  padding: 0 5px;
  border-radius: 6px;
  background: rgba(8, 18, 26, 0.7);
  color: #cdd8dd;
  font-size: 0.8rem;
}
.dcard__body { display: flex; flex-direction: column; gap: 5px; padding: 14px 16px 16px; }
.dcard__title { font-size: 1.04rem; font-weight: 800; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dcard__loc { font-size: 0.72rem; color: #7f97a1; }
.dcard__desc {
  margin-top: 2px;
  font-size: 0.84rem;
  line-height: 1.45;
  color: #9fb4bf;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>

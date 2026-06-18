<template>
  <div
    class="ucard"
    :class="{ 'ucard--disabled': isDisabled || isDeleting, 'ucard--busy': isDeleting }"
    :style="{ '--accent': accent }"
  >
    <span class="ucard__rail" aria-hidden="true"></span>

    <div class="ucard__head">
      <div class="ucard__heading">
        <span v-if="kind" class="ucard__kind">{{ kind }}</span>
        <v-tooltip :text="title" location="top" open-delay="250" :disabled="!truncated">
          <template #activator="{ props: tip }">
            <span ref="titleEl" class="ucard__name" v-bind="tip">{{ title }}</span>
          </template>
        </v-tooltip>
      </div>

      <v-menu v-if="menuItems.length" v-model="menu" location="bottom end" :offset="8">
        <template #activator="{ props: act }">
          <button
            type="button"
            class="ucard__more"
            :class="{ 'is-open': menu }"
            v-bind="act"
            aria-label="More actions"
          >
            <v-icon icon="mdi-dots-horizontal" size="18" />
          </button>
        </template>
        <div class="ucard-menu">
          <button
            v-for="(item, i) in menuItems"
            :key="i"
            type="button"
            class="ucard-menu__item"
            :class="{ 'is-danger': item.danger }"
            :disabled="item.disabled"
            @click="run(item)"
          >
            <v-icon v-if="item.icon" :icon="item.icon" size="16" class="ucard-menu__icon" />
            <span>{{ item.label }}</span>
          </button>
        </div>
      </v-menu>
    </div>

    <p v-if="$slots.description" class="ucard__desc"><slot name="description" /></p>

    <div class="ucard__foot">
      <div class="ucard__meta"><slot name="meta" /></div>
      <div v-if="$slots.action" class="ucard__cta"><slot name="action" /></div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from "vue";

export interface UCardMenuItem {
  label: string;
  icon?: string;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
}

const props = withDefaults(
  defineProps<{
    title: string;
    kind?: string;
    accent?: string;
    isDeleting?: boolean;
    isDisabled?: boolean;
    menuItems?: UCardMenuItem[];
  }>(),
  {
    accent: "#5fd6e8",
    isDeleting: false,
    isDisabled: false,
    menuItems: () => [],
  },
);

const menu = ref(false);

// Show the title tooltip only when the single-line name is actually clipped —
// no tooltip on short names. Re-measured on resize + title change.
const titleEl = ref<HTMLElement>();
const truncated = ref(false);
let ro: ResizeObserver | undefined;
const measure = () => {
  const el = titleEl.value;
  if (el) truncated.value = el.scrollWidth > el.clientWidth + 1;
};
onMounted(() => {
  measure();
  if (typeof ResizeObserver !== "undefined" && titleEl.value) {
    ro = new ResizeObserver(measure);
    ro.observe(titleEl.value);
  }
});
watch(() => props.title, () => nextTick(measure));
onBeforeUnmount(() => ro?.disconnect());

const run = (item: UCardMenuItem) => {
  if (item.disabled) return;
  menu.value = false;
  item.onClick();
};
</script>

<style scoped>
.ucard {
  --accent: #5fd6e8;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  min-height: 188px;
  padding: 20px 20px 18px;
  border-radius: 16px;
  border: 1px solid rgba(120, 200, 220, 0.14);
  background: rgba(255, 255, 255, 0.028);
  font-family: "Nunito", sans-serif;
  color: #e9f2f5;
  overflow: hidden;
  transition: transform 0.4s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.4s ease, background 0.4s ease;
}
.ucard__rail {
  position: absolute;
  top: 0;
  left: 20px;
  right: 20px;
  height: 2px;
  border-radius: 2px;
  background: var(--accent);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}
.ucard:hover {
  transform: translateY(-4px);
  border-color: color-mix(in srgb, var(--accent) 40%, transparent);
  background: rgba(255, 255, 255, 0.045);
}
.ucard:hover .ucard__rail { transform: scaleX(1); }
.ucard--disabled { opacity: 0.5; pointer-events: none; }
.ucard--busy .ucard__rail { transform: scaleX(1); animation: ucard-busy 1s ease-in-out infinite; }
@keyframes ucard-busy { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }

.ucard__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.ucard__heading { display: flex; flex-direction: column; gap: 5px; min-width: 0; flex: 1; }
.ucard__kind {
  font-size: 0.64rem;
  font-weight: 700;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--accent);
  opacity: 0.9;
}
.ucard__name {
  font-size: 1.12rem;
  font-weight: 800;
  line-height: 1.25;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.ucard__more {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 9px;
  border: 1px solid rgba(120, 200, 220, 0.18);
  background: rgba(255, 255, 255, 0.03);
  color: #a4bac4;
  cursor: pointer;
  transition: border-color 0.25s ease, color 0.25s ease, background 0.25s ease;
}
.ucard__more:hover,
.ucard__more.is-open {
  border-color: color-mix(in srgb, var(--accent) 50%, transparent);
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 9%, transparent);
}

.ucard__desc {
  margin: 0;
  flex: 1;
  font-size: 0.84rem;
  line-height: 1.5;
  color: #9fb4bf;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ucard__foot {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-top: 6px;
}
.ucard__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-width: 0; }
.ucard__cta { flex-shrink: 0; }

/* Dropdown — teleported, but the wrapper is rendered by THIS component so the
   scoped attribute (and these rules) still apply. */
.ucard-menu {
  min-width: 210px;
  padding: 6px;
  border-radius: 13px;
  background: rgba(8, 18, 26, 0.98);
  border: 1px solid rgba(95, 214, 232, 0.2);
  box-shadow: 0 18px 40px -16px rgba(0, 0, 0, 0.8);
}
.ucard-menu__item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 11px;
  border: none;
  border-radius: 9px;
  background: transparent;
  color: #cddae0;
  font-family: "Nunito", sans-serif;
  font-size: 0.85rem;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}
.ucard-menu__item:hover:not(:disabled) { background: rgba(95, 214, 232, 0.1); color: #fff; }
.ucard-menu__item:disabled { opacity: 0.4; cursor: not-allowed; }
.ucard-menu__icon { color: #7f97a1; transition: color 0.18s ease; }
.ucard-menu__item:hover:not(:disabled) .ucard-menu__icon { color: #5fd6e8; }
.ucard-menu__item.is-danger { color: #f0a6a6; }
.ucard-menu__item.is-danger:hover:not(:disabled) { background: rgba(255, 107, 107, 0.12); color: #ff8585; }
.ucard-menu__item.is-danger .ucard-menu__icon { color: #d98c8c; }
</style>

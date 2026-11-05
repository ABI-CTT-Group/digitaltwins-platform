<template>
  <div
    class="ucard"
    :class="{ 'ucard--disabled': isDisabled }"
    :style="{ '--accent': accent }"
  >
    <span class="ucard__rail" aria-hidden="true"></span>

    <div class="ucard__head">
      <div class="ucard__heading">
        <span v-if="kind" class="ucard__kind">{{ kind }}</span>
        <!-- Always show the full name on hover: card titles are routinely
             clipped (ellipsis) and the truncation-detection was unreliable, so
             the user couldn't tell which tool a card was. Native `title` attr is
             a guaranteed fallback even if the v-tooltip teleport misbehaves. -->
        <v-tooltip :text="title" location="top" open-delay="200">
          <template #activator="{ props: tip }">
            <span class="ucard__name" :title="title" v-bind="tip">{{ title }}</span>
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
import { ref } from "vue";

export interface UCardMenuItem {
  label: string;
  icon?: string;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
}

withDefaults(
  defineProps<{
    title: string;
    kind?: string;
    accent?: string;
    isDisabled?: boolean;
    menuItems?: UCardMenuItem[];
  }>(),
  {
    accent: "var(--accent-tools)",
    isDisabled: false,
    menuItems: () => [],
  },
);

const menu = ref(false);

const run = (item: UCardMenuItem) => {
  if (item.disabled) return;
  menu.value = false;
  item.onClick();
};
</script>

<style scoped>
/* Quiet by default: no shadow, no lift. The category accent marks only the top edge and the kind
   label; status colour (later, the status line) is what draws the eye. */
.ucard {
  --accent: var(--accent-tools);
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  min-height: 188px;
  padding: 20px 20px 18px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--surface);
  font-family: var(--font-ui);
  color: var(--text);
  overflow: hidden;
  transition: border-color 0.25s ease, background 0.25s ease;
}
.ucard__rail {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--accent);
  opacity: 0.55;
  transition: opacity 0.25s ease;
}
.ucard:hover,
.ucard:focus-within {
  border-color: color-mix(in srgb, var(--accent) 34%, transparent);
  background: rgba(255, 255, 255, 0.04);
}
.ucard:hover .ucard__rail,
.ucard:focus-within .ucard__rail { opacity: 1; }
.ucard--disabled { opacity: 0.5; pointer-events: none; }

.ucard__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.ucard__heading { display: flex; flex-direction: column; gap: 4px; min-width: 0; flex: 1; }
.ucard__kind {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--accent);
}
.ucard__name {
  font-size: 1.2rem;
  font-weight: 650;
  line-height: 1.25;
  letter-spacing: -0.005em;
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
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-dim);
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease;
}
.ucard__more:hover,
.ucard__more.is-open {
  border-color: color-mix(in srgb, var(--accent) 50%, transparent);
  color: var(--text);
}
.ucard__more:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.ucard__desc {
  margin: 0;
  flex: 1;
  max-width: 60ch;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-dim);
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
   scoped attribute (and these rules) still apply. It can't inherit the card's
   --accent, so it stays neutral. */
.ucard-menu {
  min-width: 210px;
  padding: 6px;
  border-radius: 12px;
  background: rgba(8, 18, 26, 0.98);
  border: 1px solid var(--line);
  box-shadow: 0 18px 40px -16px rgba(0, 0, 0, 0.8);
}
.ucard-menu__item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 11px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  font-family: var(--font-ui);
  font-size: 0.875rem;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease;
}
.ucard-menu__item:hover:not(:disabled),
.ucard-menu__item:focus-visible { background: rgba(255, 255, 255, 0.06); outline: none; }
.ucard-menu__item:disabled { opacity: 0.4; cursor: not-allowed; }
.ucard-menu__icon { color: var(--text-faint); }
.ucard-menu__item:hover:not(:disabled) .ucard-menu__icon { color: var(--text); }
.ucard-menu__item.is-danger { color: var(--tone-failed); }
.ucard-menu__item.is-danger .ucard-menu__icon { color: var(--tone-failed); }
.ucard-menu__item.is-danger:hover:not(:disabled) { background: color-mix(in srgb, var(--tone-failed) 12%, transparent); }
</style>

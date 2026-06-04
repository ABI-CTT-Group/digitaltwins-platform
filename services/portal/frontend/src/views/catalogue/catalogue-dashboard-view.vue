<template>
  <section class="catalogue">
    <div class="catalogue__inner">

      <!-- Header -->
      <header class="masthead">
        <p class="masthead__eyebrow">DigitalTWINS · AI Platform</p>
        <h1 class="masthead__title">Catalogue</h1>
        <p class="masthead__sub">
          Your gateway to descriptions, datasets and workflow tooling across the platform.
        </p>
      </header>

      <!-- Hero: SEEK -->
      <button
        type="button"
        class="hero"
        :class="{ 'is-busy': activeHref === hero.herf }"
        @click="navigate(hero)"
      >
        <span class="hero__glow" aria-hidden="true"></span>
        <span class="hero__icon">
          <v-icon :icon="hero.icon" size="34"></v-icon>
        </span>
        <span class="hero__body">
          <span class="hero__eyebrow">External · Research catalogue</span>
          <span class="hero__title">{{ hero.title }}</span>
          <span class="hero__desc">{{ hero.description }}</span>
        </span>
        <span class="hero__cta">
          <span class="hero__cta-label">Open SEEK</span>
          <v-icon icon="mdi-arrow-top-right" size="22"></v-icon>
        </span>
      </button>

      <!-- Action grid -->
      <div class="grid">
        <button
          v-for="(card, i) in actions"
          :key="card.herf"
          type="button"
          class="tile"
          :class="{ 'is-busy': activeHref === card.herf }"
          :style="{ '--accent': card.accent, '--delay': `${120 + i * 80}ms` }"
          @click="navigate(card)"
        >
          <span class="tile__rail" aria-hidden="true"></span>
          <span class="tile__top">
            <span class="tile__icon">
              <v-icon :icon="card.icon" size="26"></v-icon>
            </span>
            <span v-if="card.requireRoles" class="tile__roles">
              <v-icon icon="mdi-lock-outline" size="12"></v-icon>
              {{ card.requireRoles.join(' · ') }}
            </span>
          </span>

          <span class="tile__title">{{ card.title }}</span>
          <span class="tile__desc">{{ card.description }}</span>

          <span class="tile__cta">
            <span>{{ card.cta }}</span>
            <v-icon icon="mdi-arrow-right" size="18"></v-icon>
          </span>

          <span class="tile__index" aria-hidden="true">{{ pad(i + 1) }}</span>
        </button>
      </div>

    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthGuard } from '@/composables/useAuthGuard';

type CatalogueCard = {
  title: string;
  description: string;
  herf: string;
  icon: string;
  cta: string;
  accent?: string;
  external?: boolean;
  requireRoles?: string[];
};

const hero: CatalogueCard = {
  title: 'SEEK Catalogue',
  description:
    'Browse and author descriptions for programmes, projects, investigations, studies and assays — and explore the workflows and tools already on the platform.',
  herf: import.meta.env.VITE_SEEK_URL,
  icon: 'mdi-database-search-outline',
  cta: 'Open SEEK',
  external: true,
};

const actions: CatalogueCard[] = [
  {
    title: 'Upload workflow tool',
    description: 'Register a new workflow tool and make it available across the platform.',
    herf: 'UploadToolDataset',
    icon: 'mdi-wrench-outline',
    cta: 'Upload',
    accent: '#5fd6e8',
    requireRoles: ['admin'],
  },
  {
    title: 'Upload workflow',
    description: 'Publish a new workflow definition to the platform registry.',
    herf: 'UploadWorkflowDataset',
    icon: 'mdi-sitemap-outline',
    cta: 'Upload',
    accent: '#62d3b0',
    requireRoles: ['admin'],
  },
  {
    title: 'Upload measurements',
    description:
      'Upload a SPARC measurements dataset — register patients, observations, imaging studies and document references.',
    herf: 'UploadMeasurementsDataset',
    icon: 'mdi-chart-box-outline',
    cta: 'Upload',
    accent: '#7fb2f0',
    requireRoles: ['admin', 'researcher'],
  },
  {
    title: 'Workflow assembler',
    description: 'Assemble and publish a new workflow to the platform, step by step.',
    herf: 'WorkflowToolsViewer',
    icon: 'mdi-vector-combine',
    cta: 'Open',
    accent: '#9fd0e6',
  },
];

const router = useRouter();
const activeHref = ref<string | null>(null);

const pad = (n: number) => String(n).padStart(2, '0');

const navigate = async (card: CatalogueCard) => {
  if (card.requireRoles) {
    const { check } = useAuthGuard();
    if (!check(card.requireRoles.length ? card.requireRoles : undefined)) return;
  }

  activeHref.value = card.herf;

  if (card.external || card.herf?.startsWith('http')) {
    window.open(card.herf, '_blank');
    setTimeout(() => { activeHref.value = null; }, 800);
    return;
  }

  try {
    await router.push({ name: card.herf });
  } catch (e) {
    console.error(e);
  } finally {
    activeHref.value = null;
  }
};
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');

.catalogue {
  --ink: #07131b;
  --aqua: #5fd6e8;
  --text: #e9f2f5;
  --text-dim: #a4bac4;
  --text-faint: #5f7884;
  --line: rgba(120, 200, 220, 0.14);
  --surface: rgba(255, 255, 255, 0.028);

  position: relative;
  min-height: 100%;
  padding: clamp(28px, 6vh, 72px) clamp(20px, 5vw, 80px) 64px;
  font-family: 'Hanken Grotesk', system-ui, sans-serif;
  color: var(--text);
  /* Background (aurora glow + masked grid + breathing) is provided once by
     .page-aurora in layouts/View.vue, so every page shares the exact look. */
}

.catalogue__inner {
  position: relative;
  max-width: 1120px;
  margin: 0 auto;
}

/* ---- Masthead ---- */
.masthead {
  margin-bottom: clamp(28px, 5vh, 52px);
  animation: rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.masthead__eyebrow {
  margin: 0 0 14px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--aqua);
  opacity: 0.85;
}
.masthead__title {
  margin: 0;
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  font-size: clamp(2.6rem, 6vw, 4.4rem);
  line-height: 0.98;
  letter-spacing: -0.015em;
  color: #fff;
}
.masthead__sub {
  margin: 16px 0 0;
  max-width: 46ch;
  font-size: clamp(0.95rem, 1.4vw, 1.08rem);
  line-height: 1.55;
  color: var(--text-dim);
}

/* ---- Shared button reset ---- */
.hero,
.tile {
  appearance: none;
  text-align: left;
  border: none;
  cursor: pointer;
  font-family: inherit;
  color: inherit;
  width: 100%;
}
.is-busy { cursor: progress; }

/* ---- Hero (SEEK) ---- */
.hero {
  position: relative;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: clamp(20px, 3vw, 40px);
  padding: clamp(26px, 3.4vw, 40px) clamp(26px, 3.4vw, 44px);
  margin-bottom: clamp(22px, 3vh, 34px);
  border-radius: 20px;
  border: 1px solid var(--line);
  background:
    linear-gradient(135deg, rgba(31, 183, 217, 0.10), rgba(255, 255, 255, 0.02) 45%),
    var(--surface);
  backdrop-filter: blur(8px);
  overflow: hidden;
  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.4s ease, box-shadow 0.45s ease;
  animation: rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) 80ms both;
}
.hero__glow {
  position: absolute;
  inset: -1px;
  background: radial-gradient(420px 200px at 88% 50%, rgba(95, 214, 232, 0.16), transparent 70%);
  opacity: 0.7;
  transition: opacity 0.45s ease;
  pointer-events: none;
}
.hero:hover {
  transform: translateY(-3px);
  border-color: rgba(95, 214, 232, 0.42);
  box-shadow: 0 24px 60px -28px rgba(0, 0, 0, 0.8);
}
.hero:hover .hero__glow { opacity: 1; }
.hero__icon {
  display: grid;
  place-items: center;
  width: 64px;
  height: 64px;
  border-radius: 16px;
  color: var(--aqua);
  background: rgba(95, 214, 232, 0.1);
  border: 1px solid rgba(95, 214, 232, 0.28);
}
.hero__body { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
.hero__eyebrow {
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--text-faint);
}
.hero__title {
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  font-size: clamp(1.5rem, 2.6vw, 2.05rem);
  line-height: 1.05;
  color: #fff;
}
.hero__desc {
  font-size: 0.95rem;
  line-height: 1.55;
  color: var(--text-dim);
  max-width: 62ch;
}
.hero__cta {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-radius: 999px;
  white-space: nowrap;
  font-weight: 600;
  font-size: 0.92rem;
  color: var(--ink);
  background: var(--aqua);
  box-shadow: 0 0 0 0 rgba(95, 214, 232, 0.5);
  transition: box-shadow 0.4s ease, transform 0.4s ease;
}
.hero:hover .hero__cta {
  box-shadow: 0 12px 30px -10px rgba(95, 214, 232, 0.6);
  transform: translateX(2px);
}

/* ---- Action grid ---- */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(248px, 1fr));
  gap: clamp(14px, 1.6vw, 20px);
}
.tile {
  --accent: var(--aqua);
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 212px;
  padding: 24px 24px 22px;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: var(--surface);
  overflow: hidden;
  transition: transform 0.4s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.4s ease, background 0.4s ease;
  animation: rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) var(--delay, 0ms) both;
}
.tile__rail {
  position: absolute;
  top: 0;
  left: 22px;
  right: 22px;
  height: 2px;
  border-radius: 2px;
  background: var(--accent);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}
.tile:hover {
  transform: translateY(-4px);
  border-color: color-mix(in srgb, var(--accent) 45%, transparent);
  background: rgba(255, 255, 255, 0.045);
}
.tile:hover .tile__rail { transform: scaleX(1); }

.tile__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.tile__icon {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 12px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 26%, transparent);
}
.tile__roles {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-dim);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--line);
}
.tile__title {
  font-size: 1.12rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: #fff;
}
.tile__desc {
  flex: 1;
  font-size: 0.86rem;
  line-height: 1.5;
  color: var(--text-dim);
}
.tile__cta {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--accent);
}
.tile__cta .v-icon {
  transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}
.tile:hover .tile__cta .v-icon { transform: translateX(5px); }
.tile__index {
  position: absolute;
  top: 18px;
  right: 22px;
  font-family: 'Fraunces', Georgia, serif;
  font-size: 1.1rem;
  font-weight: 400;
  color: var(--text-faint);
  opacity: 0.45;
}
/* hide the index when a role badge occupies the same corner */
.tile:has(.tile__roles) .tile__index { display: none; }

@keyframes rise {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}

@media (max-width: 720px) {
  .hero { grid-template-columns: auto 1fr; }
  .hero__cta { grid-column: 1 / -1; justify-content: center; }
}

@media (prefers-reduced-motion: reduce) {
  .masthead, .hero, .tile { animation: none; }
  .hero, .tile, .tile__cta .v-icon, .tile__rail { transition: none; }
}
</style>

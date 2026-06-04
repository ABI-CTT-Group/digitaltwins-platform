<template>
  <section class="tutorial">
    <div class="tutorial__inner">

      <header class="masthead">
        <p class="masthead__eyebrow">DigitalTWINS · Documentation</p>
        <h1 class="masthead__title">How It Works</h1>
        <p class="masthead__sub">
          Guides, API references and resources to help you get the most out of the platform.
        </p>
      </header>

      <section
        v-for="(section, i) in decoratedSections"
        :key="section.title"
        class="doc-section"
        :style="{ '--accent': section.accent }"
      >
        <div class="doc-section__head">
          <span class="doc-section__bar" aria-hidden="true"></span>
          <v-icon :icon="section.icon" size="20" class="doc-section__icon"></v-icon>
          <h2 class="doc-section__title">{{ section.title }}</h2>
          <span class="doc-section__count">{{ section.items.length }}</span>
        </div>

        <div class="doc-grid">
          <a
            v-for="(item, j) in section.items"
            :key="item.title"
            class="doc-card"
            :class="{ 'is-disabled': !item.herf }"
            :href="item.herf || undefined"
            target="_blank"
            rel="noopener noreferrer"
            :style="{ '--delay': `${i * 60 + j * 55}ms` }"
          >
            <span class="doc-card__icon">
              <v-icon :icon="section.icon" size="22"></v-icon>
            </span>
            <span class="doc-card__body">
              <span class="doc-card__title">{{ item.title }}</span>
              <span class="doc-card__meta">{{ item.herf ? 'External resource' : 'Link unavailable' }}</span>
            </span>
            <v-icon icon="mdi-arrow-top-right" size="18" class="doc-card__arrow"></v-icon>
          </a>
        </div>
      </section>

    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { sections, SectionConfig } from './tutorial.config';

type SectionMeta = { icon: string; accent: string };

const META: Record<string, SectionMeta> = {
  'Help documentation': { icon: 'mdi-book-open-variant', accent: '#5fd6e8' },
  'API documentation': { icon: 'mdi-api', accent: '#62d3b0' },
  'Guidelines': { icon: 'mdi-clipboard-text-outline', accent: '#7fb2f0' },
  'Resources': { icon: 'mdi-toolbox-outline', accent: '#9fd0e6' },
};

const FALLBACK: SectionMeta[] = [
  { icon: 'mdi-book-open-variant', accent: '#5fd6e8' },
  { icon: 'mdi-api', accent: '#62d3b0' },
  { icon: 'mdi-clipboard-text-outline', accent: '#7fb2f0' },
  { icon: 'mdi-toolbox-outline', accent: '#9fd0e6' },
];

const decoratedSections = computed(() =>
  sections.map((s: SectionConfig, i: number) => ({
    ...s,
    ...(META[s.title] ?? FALLBACK[i % FALLBACK.length]),
  }))
);
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');

.tutorial {
  --text: #e9f2f5;
  --text-dim: #a4bac4;
  --text-faint: #5f7884;
  --line: rgba(120, 200, 220, 0.14);
  --surface: rgba(255, 255, 255, 0.028);

  min-height: 100%;
  padding: clamp(28px, 6vh, 72px) clamp(20px, 5vw, 80px) 72px;
  font-family: 'Hanken Grotesk', system-ui, sans-serif;
  color: var(--text);
  /* transparent — sits on the shared aurora backdrop */
}

.tutorial__inner {
  max-width: 1120px;
  margin: 0 auto;
}

/* ---- Masthead ---- */
.masthead {
  margin-bottom: clamp(32px, 6vh, 60px);
  animation: rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.masthead__eyebrow {
  margin: 0 0 14px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: #5fd6e8;
  opacity: 0.85;
}
.masthead__title {
  margin: 0;
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  font-size: clamp(2.4rem, 5.5vw, 4rem);
  line-height: 1;
  letter-spacing: -0.015em;
  color: #fff;
}
.masthead__sub {
  margin: 16px 0 0;
  max-width: 52ch;
  font-size: clamp(0.95rem, 1.4vw, 1.08rem);
  line-height: 1.55;
  color: var(--text-dim);
}

/* ---- Section ---- */
.doc-section {
  --accent: #5fd6e8;
  margin-bottom: clamp(30px, 5vh, 48px);
}
.doc-section__head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}
.doc-section__bar {
  width: 22px;
  height: 2px;
  border-radius: 2px;
  background: var(--accent);
}
.doc-section__icon {
  color: var(--accent);
}
.doc-section__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: #fff;
}
.doc-section__count {
  display: grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-faint);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--line);
}

/* ---- Cards ---- */
.doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: clamp(12px, 1.4vw, 18px);
}
.doc-card {
  --accent: inherit;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 20px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: var(--surface);
  text-decoration: none;
  color: inherit;
  /* cheap hover — transform/border/colour only, NO backdrop-filter, NO mask */
  transition: transform 0.32s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.32s ease, background 0.32s ease;
  animation: rise 0.6s cubic-bezier(0.22, 1, 0.36, 1) var(--delay, 0ms) both;
}
.doc-card:hover {
  transform: translateY(-3px);
  border-color: color-mix(in srgb, var(--accent) 48%, transparent);
  background: rgba(255, 255, 255, 0.05);
}
.doc-card__icon {
  flex: none;
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 11px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 26%, transparent);
}
.doc-card__body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}
.doc-card__title {
  font-size: 0.96rem;
  font-weight: 600;
  line-height: 1.3;
  color: #fff;
}
.doc-card__meta {
  font-size: 0.74rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-faint);
}
.doc-card__arrow {
  flex: none;
  color: var(--accent);
  opacity: 0.7;
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.3s ease;
}
.doc-card:hover .doc-card__arrow {
  opacity: 1;
  transform: translate(3px, -3px);
}
.doc-card.is-disabled {
  opacity: 0.45;
  pointer-events: none;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .masthead, .doc-card { animation: none; }
  .doc-card, .doc-card__arrow { transition: none; }
}
</style>

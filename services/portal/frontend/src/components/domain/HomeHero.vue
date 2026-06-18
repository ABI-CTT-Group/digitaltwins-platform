<template>
  <section class="hero">
    <div class="hero__bg" aria-hidden="true">
      <HeartHologram class="hero__heart" />
      <div class="hero__scrim"></div>
    </div>

    <div class="hero__inner">
      <p class="hero__eyebrow">DigitalTWINS AI Platform</p>
      <h1 class="hero__title">{{ title }}</h1>
      <p class="hero__sub">{{ subtitle }}</p>
      <div class="hero__cta">
        <button type="button" class="hero__btn hero__btn--primary" @click="$emit('enter')">Enter the platform</button>
        <button type="button" class="hero__btn hero__btn--ghost" @click="$emit('how-it-works')">How it works</button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { defineAsyncComponent } from 'vue';

// Lazy-loaded so Three.js + the heart mesh split into their own chunk and only
// download when the landing hero mounts (kept out of the main app bundle).
const HeartHologram = defineAsyncComponent(() => import('@/components/domain/HeartHologram.vue'));

defineProps({
  title: {
    type: String,
    default: 'Accelerating Development of Digital Twin and AI-Driven Workflows',
  },
  subtitle: {
    type: String,
    default: 'Seamlessly integrate digital twin and AI technologies into clinical and research environments',
  },
});
defineEmits<{ (e: 'enter'): void; (e: 'how-it-works'): void }>();
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500&display=swap');

.hero { position: relative; overflow: hidden; padding: clamp(48px, 9vh, 96px) 20px clamp(40px, 7vh, 72px); text-align: center; }
.hero__bg { position: absolute; inset: 0; z-index: 0; pointer-events: none; }
/* let drags pass through the text to the heart canvas; buttons stay clickable */
.hero__inner { position: relative; z-index: 2; pointer-events: none; }
.hero__cta { pointer-events: auto; }

.hero__eyebrow { margin: 0 0 14px; color: #7fe2f0; letter-spacing: 0.34em; font-size: 0.72rem; text-transform: uppercase; font-family: "Nunito", sans-serif; text-shadow: 0 0 14px rgba(95,214,232,.4); }
.hero__title { margin: 0 auto; max-width: 22ch; font-family: 'Fraunces', Georgia, serif; font-weight: 500; font-size: clamp(2rem, 5vw, 3.4rem); line-height: 1.12; letter-spacing: -0.01em; color: #fff; text-shadow: 0 2px 36px rgba(0,0,0,.7), 0 0 28px rgba(95,214,232,.10); }
.hero__sub { margin: 16px auto 24px; max-width: 48ch; color: #b9cad1; font-size: clamp(0.95rem, 1.4vw, 1.08rem); line-height: 1.55; font-family: "Nunito", sans-serif; }
.hero__cta { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.hero__btn { font-family: "Nunito", sans-serif; font-weight: 600; font-size: 0.92rem; border-radius: 9px; padding: 10px 22px; cursor: pointer; transition: transform 0.25s ease, background 0.25s ease, border-color 0.25s ease; }
.hero__btn--primary { background: #e6edf0; color: #0a1018; border: 1px solid transparent; }
.hero__btn--primary:hover { background: #fff; transform: translateY(-1px); }
.hero__btn--ghost { background: transparent; color: #e6edf0; border: 1px solid rgba(180, 210, 220, 0.34); }
.hero__btn--ghost:hover { border-color: rgba(95, 214, 232, 0.55); }

/* ---- one-time entrance choreography: eyebrow → title → sub → CTA rise in ---- */
.hero__eyebrow { animation: hero-rise .7s cubic-bezier(.22,1,.36,1) both; animation-delay: .06s; }
.hero__title   { animation: hero-rise .8s cubic-bezier(.22,1,.36,1) both; animation-delay: .16s; }
.hero__sub     { animation: hero-rise .8s cubic-bezier(.22,1,.36,1) both; animation-delay: .30s; }
.hero__cta     { animation: hero-rise .8s cubic-bezier(.22,1,.36,1) both; animation-delay: .42s; }
@keyframes hero-rise { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: none; } }

/* primary CTA: a faint breathing glow + a one-off sheen sweep on hover */
.hero__btn--primary { position: relative; overflow: hidden; animation: cta-breathe 3.6s ease-in-out 1.3s infinite; }
.hero__btn--primary::after {
  content: ""; position: absolute; top: 0; left: -70%; width: 55%; height: 100%; pointer-events: none;
  background: linear-gradient(100deg, transparent, rgba(120,225,245,.55), transparent);
  transform: skewX(-18deg); opacity: 0;
}
.hero__btn--primary:hover::after { animation: cta-sheen .75s ease; }
@keyframes cta-breathe {
  0%, 100% { box-shadow: 0 4px 18px rgba(0,0,0,.18); }
  50%      { box-shadow: 0 4px 18px rgba(0,0,0,.18), 0 0 22px rgba(95,214,232,.30); }
}
@keyframes cta-sheen { 0% { left: -70%; opacity: 0; } 25% { opacity: 1; } 100% { left: 130%; opacity: 0; } }

@media (prefers-reduced-motion: reduce) {
  .hero__eyebrow, .hero__title, .hero__sub, .hero__cta, .hero__btn--primary { animation: none; }
}

/* the transparent WebGL heart fills the hero, page backdrop shows through */
.hero__heart {
  position: absolute;
  inset: 0;
}

/* scrim: lifts the title + subtitle off the hologram so the text stays crisp */
.hero__scrim {
  position: absolute; inset: 0;
  background: radial-gradient(ellipse 56% 46% at 50% 40%, rgba(6,12,20,.62), transparent 72%);
}
</style>

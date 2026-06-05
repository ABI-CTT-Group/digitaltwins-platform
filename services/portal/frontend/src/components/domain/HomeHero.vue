<template>
  <section class="hero">
    <div class="hero__bg" aria-hidden="true">
      <div class="hero__aurora"></div>
      <div class="hero__ring hero__ring--1"></div>
      <div class="hero__ring hero__ring--2"></div>
      <div class="hero__ring hero__ring--3"></div>
      <span class="hero__pulse"></span><span class="hero__pulse hero__pulse--b"></span>
      <span class="hero__node n1"></span><span class="hero__node n2"></span><span class="hero__node n3"></span>
      <span class="hero__node n4"></span><span class="hero__node n5"></span><span class="hero__node n6"></span>
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
.hero__inner { position: relative; z-index: 2; }

.hero__eyebrow { margin: 0 0 14px; color: #5fd6e8; letter-spacing: 0.32em; font-size: 0.7rem; text-transform: uppercase; font-family: "Nunito", sans-serif; }
.hero__title { margin: 0 auto; max-width: 22ch; font-family: 'Fraunces', Georgia, serif; font-weight: 500; font-size: clamp(2rem, 5vw, 3.4rem); line-height: 1.12; letter-spacing: -0.01em; color: #fff; text-shadow: 0 2px 40px rgba(0,0,0,.5); }
.hero__sub { margin: 16px auto 24px; max-width: 48ch; color: #b9cad1; font-size: clamp(0.95rem, 1.4vw, 1.08rem); line-height: 1.55; font-family: "Nunito", sans-serif; }
.hero__cta { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.hero__btn { font-family: "Nunito", sans-serif; font-weight: 600; font-size: 0.92rem; border-radius: 9px; padding: 10px 22px; cursor: pointer; transition: transform 0.25s ease, background 0.25s ease, border-color 0.25s ease; }
.hero__btn--primary { background: #e6edf0; color: #0a1018; border: 1px solid transparent; }
.hero__btn--primary:hover { background: #fff; transform: translateY(-1px); }
.hero__btn--ghost { background: transparent; color: #e6edf0; border: 1px solid rgba(180, 210, 220, 0.34); }
.hero__btn--ghost:hover { border-color: rgba(95, 214, 232, 0.55); }

/* ---- animated backdrop (transform/opacity + drifting glow) ---- */
.hero__aurora {
  position: absolute; inset: -20%;
  background:
    radial-gradient(40% 35% at 50% 8%, rgba(58,170,215,.34), transparent 60%),
    radial-gradient(30% 28% at 22% 30%, rgba(95,214,232,.18), transparent 60%),
    radial-gradient(34% 30% at 80% 22%, rgba(120,90,220,.16), transparent 60%);
  animation: hero-sweep 18s ease-in-out infinite alternate;
}
@keyframes hero-sweep { 0% { transform: translate(-2%,-1%) scale(1); } 100% { transform: translate(3%,2%) scale(1.08); } }

.hero__ring { position: absolute; top: 42%; left: 50%; border-radius: 50%; border: 1px solid rgba(120,200,220,.14); }
.hero__ring--1 { width: 240px; height: 240px; margin: -120px 0 0 -120px; animation: hero-spin 34s linear infinite; }
.hero__ring--2 { width: 360px; height: 360px; margin: -180px 0 0 -180px; border-style: dashed; border-color: rgba(120,200,220,.10); animation: hero-spin 52s linear infinite reverse; }
.hero__ring--3 { width: 150px; height: 150px; margin: -75px 0 0 -75px; border-color: rgba(95,214,232,.22); animation: hero-spin 22s linear infinite; }
.hero__ring::after { content: ""; position: absolute; top: -3px; left: 50%; width: 7px; height: 7px; margin-left: -3px; border-radius: 50%; background: #5fd6e8; box-shadow: 0 0 12px rgba(95,214,232,.8); }
.hero__ring--2::after { background: #9fb4bf; box-shadow: 0 0 8px rgba(160,190,200,.5); }
@keyframes hero-spin { to { transform: rotate(360deg); } }

.hero__pulse { position: absolute; top: 42%; left: 50%; width: 40px; height: 40px; margin: -20px 0 0 -20px; border-radius: 50%; border: 1px solid rgba(95,214,232,.4); animation: hero-pulse 5s ease-out infinite; }
.hero__pulse--b { animation-delay: 2.5s; }
@keyframes hero-pulse { 0% { transform: scale(.4); opacity: .7; } 100% { transform: scale(4.2); opacity: 0; } }

.hero__node { position: absolute; border-radius: 50%; background: #9fb4bf; }
.hero__node.n1 { width: 6px; height: 6px; top: 24%; left: 18%; animation: hero-dr 9s ease-in-out infinite; }
.hero__node.n2 { width: 5px; height: 5px; top: 60%; left: 26%; animation: hero-dr 12s ease-in-out infinite reverse; }
.hero__node.n3 { width: 7px; height: 7px; top: 30%; left: 80%; background: #5fd6e8; animation: hero-dr 10s ease-in-out infinite; }
.hero__node.n4 { width: 4px; height: 4px; top: 66%; left: 74%; animation: hero-pu 5s ease-in-out infinite; }
.hero__node.n5 { width: 5px; height: 5px; top: 16%; left: 58%; animation: hero-pu 7s ease-in-out infinite; }
.hero__node.n6 { width: 4px; height: 4px; top: 74%; left: 48%; background: #5fd6e8; animation: hero-pu 6s ease-in-out infinite; }
@keyframes hero-dr { 0%,100% { transform: translate(0,0); opacity: .5; } 50% { transform: translate(12px,-10px); opacity: 1; } }
@keyframes hero-pu { 0%,100% { opacity: .2; } 50% { opacity: .95; } }

@media (prefers-reduced-motion: reduce) {
  .hero__aurora, .hero__ring, .hero__pulse, .hero__node { animation: none !important; }
}
</style>

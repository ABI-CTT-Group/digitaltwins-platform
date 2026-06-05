<template>
    <div class="home">
        <HomeHero @enter="scrollToLaunchpad" @how-it-works="goTutorial" />

        <section id="launchpad" ref="launchpad" class="home__launchpad">
            <div class="home__grid">
                <!-- DigitalTWINS track: two light bands (aqua + magenta = the twin
                     pair) chase each other around the grid's rounded outer track. -->
                <span class="twin-track" aria-hidden="true"></span>

                <DashboardCard
                    v-for="(card, i) in cards"
                    :key="i"
                    :src="card.image"
                    :title="card.title"
                    :location="card.location"
                    :description="card.description"
                    :external="card.action?.type === 'external'"
                    :locked="isLocked(card)"
                    @on-explore="() => dispatch(card)"
                />
            </div>
        </section>

        <HomeFooter />
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthGuard } from '@/composables/useAuthGuard';
import { useAuthStore } from '@/store/auth_store';
import { cards, CardConfig } from './home.cards';
import HomeHero from '@/components/domain/HomeHero.vue';
import DashboardCard from '@/components/domain/DashboardCard.vue';
import HomeFooter from '@/components/domain/HomeFooter.vue';

const router = useRouter();
const { check } = useAuthGuard();
const authStore = useAuthStore();
const launchpad = ref<HTMLElement | null>(null);

// A card is "locked" only when the CURRENT user can't open it: it requires a
// role and the user is logged out or holds none of the required roles. So an
// admin sees no lock on cards their roles already grant.
const isLocked = (card: CardConfig): boolean => {
    if (!card.requireRoles?.length) return false;
    if (!authStore.isLoggedIn) return true;
    return !card.requireRoles.some(r => authStore.userRoles.includes(r));
};

onMounted(() => sessionStorage.removeItem('dashboardPage'));

const dispatch = (card: CardConfig) => {
    if (!check(card.requireRoles)) return;
    if (card.action?.type === 'route') router.push({ name: card.action.name, params: card.action.params });
    else if (card.action?.type === 'external') window.open(card.action.url, '_blank');
};

const scrollToLaunchpad = () => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    launchpad.value?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
};
const goTutorial = () => router.push({ name: 'TutorialDashboard' });
</script>

<style scoped>
.home { min-height: 100%; }
.home__launchpad {
    max-width: 1200px;
    margin: 0 auto;
    padding: clamp(8px, 2vh, 24px) clamp(20px, 5vw, 80px) 0;
    scroll-margin-top: 80px;
}
.home__grid {
    position: relative;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: clamp(16px, 1.8vw, 22px);
}
@media (max-width: 960px) { .home__grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px) { .home__grid { grid-template-columns: 1fr; } }

/* ---- DigitalTWINS track ----------------------------------------------------
   A masked conic-gradient ring around the grid's rounded outer frame, with two
   soft colour bands ~180° apart. Spinning the gradient angle sends both bands
   chasing each other around the track — the twin pair (real + digital) in sync. */
@property --twin-angle {
    syntax: "<angle>";
    initial-value: 0deg;
    inherits: false;
}
.twin-track {
    position: absolute;
    inset: -14px;            /* padded out from the cards */
    border-radius: 26px;     /* rounded outer track — no sharp corners */
    padding: 1.5px;          /* ring thickness */
    pointer-events: none;
    z-index: 1;
    background: conic-gradient(
        from var(--twin-angle),
        transparent 0deg 26deg,
        #5fd6e8 50deg,
        transparent 98deg 200deg,
        #cf6fc0 226deg,
        transparent 276deg 360deg
    );
    /* Keep only the 1.5px frame (gradient-border trick). */
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    filter: drop-shadow(0 0 5px rgba(120, 200, 220, 0.4));
    animation: twin-orbit 10s linear infinite;
}
@keyframes twin-orbit {
    to { --twin-angle: 360deg; }
}
@media (prefers-reduced-motion: reduce) {
    .twin-track { animation: none; opacity: 0.6; }
}
</style>

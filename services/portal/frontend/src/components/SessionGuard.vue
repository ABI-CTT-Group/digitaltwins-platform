<template>
  <div v-if="state" class="session-overlay" role="dialog" aria-modal="true" :aria-labelledby="titleId">
    <div class="session-card">
      <template v-if="state === 'idle-warning'">
        <h2 :id="titleId" class="session-title">Are you still there?</h2>
        <p class="session-body">
          You have been inactive for a while. For the safety of patient data you will be
          signed out in <strong class="session-countdown">{{ countdownLabel }}</strong>.
        </p>
        <div class="session-actions">
          <button type="button" class="session-btn session-btn--ghost" @click="handleSignOut">
            Sign out now
          </button>
          <button type="button" class="session-btn session-btn--primary" @click="handleStay">
            Stay signed in
          </button>
        </div>
      </template>

      <template v-else>
        <h2 :id="titleId" class="session-title">Your session has ended</h2>
        <p class="session-body">
          Sessions have a maximum length and yours has now been reached. Sign in again to
          return to this page — anything you have already saved is safe.
        </p>
        <div class="session-actions">
          <button type="button" class="session-btn session-btn--primary" @click="handleSignIn">
            Sign in again
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, useId } from 'vue';
import {
  SESSION_IDLE_WARNING,
  SESSION_EXPIRED,
  type IdleWarningDetail,
} from '@/bootstrap/session_events';
import { resumeSession, login, logout } from '@/bootstrap/keycloak';

type SessionState = 'idle-warning' | 'expired' | null;

const state = ref<SessionState>(null);
const secondsLeft = ref(0);
const titleId = useId();

let ticker: number | undefined;

const countdownLabel = computed(() => {
  const total = Math.max(0, secondsLeft.value);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
});

function stopTicker() {
  if (ticker) {
    clearInterval(ticker);
    ticker = undefined;
  }
}

function onIdleWarning(event: Event) {
  // An expired session is terminal — don't let a stale idle warning overwrite it.
  if (state.value === 'expired') return;

  const { secondsRemaining } = (event as CustomEvent<IdleWarningDetail>).detail;
  secondsLeft.value = secondsRemaining;
  state.value = 'idle-warning';

  stopTicker();
  ticker = window.setInterval(() => {
    secondsLeft.value -= 1;
    if (secondsLeft.value <= 0) stopTicker();
  }, 1000);
}

function onSessionExpired() {
  stopTicker();
  state.value = 'expired';
}

async function handleStay() {
  state.value = null;
  stopTicker();
  await resumeSession();
}

async function handleSignOut() {
  stopTicker();
  await logout();
}

async function handleSignIn() {
  await login();
}

onMounted(() => {
  window.addEventListener(SESSION_IDLE_WARNING, onIdleWarning);
  window.addEventListener(SESSION_EXPIRED, onSessionExpired);
});

onBeforeUnmount(() => {
  stopTicker();
  window.removeEventListener(SESSION_IDLE_WARNING, onIdleWarning);
  window.removeEventListener(SESSION_EXPIRED, onSessionExpired);
});
</script>

<style scoped>
/* Deliberately plain CSS, not Vuetify: this dialog has to be able to appear on
   every route, and /tool-view renders outside any <v-app>. */
.session-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(2, 6, 9, 0.72);
}

.session-card {
  width: 100%;
  max-width: 460px;
  padding: 28px;
  font-family: "Nunito", sans-serif;
  color: #f0f3f8;
  background: rgba(10, 29, 40, 0.92);
  border: 1px solid rgba(160, 190, 200, 0.16);
  border-radius: 20px;
  box-shadow:
    0 10px 30px rgba(0, 0, 0, 0.5),
    inset 0 0 8px rgba(255, 255, 255, 0.05);
}

.session-title {
  margin: 0 0 12px;
  font-size: 1.25rem;
  font-weight: 700;
}

.session-body {
  margin: 0 0 24px;
  font-size: 0.95rem;
  line-height: 1.55;
  color: rgba(240, 243, 248, 0.78);
}

.session-countdown {
  font-variant-numeric: tabular-nums;
  color: #f0f3f8;
}

.session-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.session-btn {
  padding: 9px 18px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.session-btn--ghost {
  color: rgba(240, 243, 248, 0.78);
  background: transparent;
  border: 1px solid rgba(160, 190, 200, 0.24);
}
.session-btn--ghost:hover {
  background: rgba(160, 190, 200, 0.1);
}

.session-btn--primary {
  color: #04212a;
  background: #4fd1c5;
  border: 1px solid transparent;
}
.session-btn--primary:hover {
  background: #6fe0d6;
}
</style>

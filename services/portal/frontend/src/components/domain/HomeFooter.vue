<template>
  <footer class="hfoot">
    <div class="hfoot__inner">
      <div class="hfoot__brand">
        <img :src="abiLogo" alt="Auckland Bioengineering Institute" class="hfoot__abi" />
        <span class="hfoot__partners">In partnership with Te Whatu Ora · SPARC</span>
      </div>
      <nav class="hfoot__links">
        <a href="#" @click.prevent="go('TutorialDashboard')">Docs</a>
        <a href="#" @click.prevent="go('CatalogueDashboardView')">Catalogue</a>
        <a :href="seekUrl" target="_blank" rel="noopener">SEEK repository</a>
      </nav>
      <div class="hfoot__legal">© {{ year }} DigitalTWINS · v{{ version }}</div>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import abiLogo from "@/assets/images/abi.png";
import { SEEK_URL } from "@/config/platform-links";

const router = useRouter();
const seekUrl = SEEK_URL;
const year = new Date().getFullYear();
const version = "3.0.0"; // from package.json
const go = (name: string) => router.push({ name });
</script>

<style scoped>
.hfoot {
  margin-top: clamp(40px, 8vh, 80px);
  border-top: 1px solid rgba(160, 190, 200, 0.12);
  font-family: "Nunito", sans-serif;
}
.hfoot__inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 26px 24px 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
}
.hfoot__brand { display: flex; align-items: center; gap: 14px; }
.hfoot__abi { height: 34px; width: auto; opacity: 0.85; filter: grayscale(0.2); }
.hfoot__partners { font-size: 0.8rem; color: #7f97a1; }
.hfoot__links { display: flex; gap: 18px; }
.hfoot__links a {
  color: #a4bac4;
  font-size: 0.82rem;
  font-weight: 600;
  text-decoration: none;
  transition: color 0.25s ease;
}
.hfoot__links a:hover { color: #5fd6e8; }
.hfoot__legal { font-size: 0.76rem; color: #6f8794; }
@media (max-width: 720px) {
  .hfoot__inner { flex-direction: column; align-items: flex-start; }
}
</style>
